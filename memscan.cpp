#define _GNU_SOURCE
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <cerrno>
#include <csignal>
#include <csetjmp>

#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>

#include <string>
#include <vector>
#include <chrono>
#include <iostream>
#include <iomanip>
#include <stdexcept>

#ifndef PAGE_SIZE
#define PAGE_SIZE 4096
#endif

#ifndef MAP_POPULATE
#define MAP_POPULATE 0x008000
#endif

struct mem_range {
    unsigned long long start;
    unsigned long long end;
};

struct scan_stats {
    unsigned long long pages   = 0;
    unsigned long long faults  = 0;
    unsigned long long skipped = 0;
};

static sigjmp_buf            g_jmp;
static volatile sig_atomic_t g_fault_addr;

static const char *sig_name(int sig)
{
    switch (sig) {
    case SIGSEGV: return "SIGSEGV";
    case SIGBUS:  return "SIGBUS";
    case SIGILL:  return "SIGILL";
    default:      return "UNKNOWN";
    }
}

static void sig_handler(int sig, siginfo_t *si, void *)
{
    g_fault_addr = (sig_atomic_t)(unsigned long)si->si_addr;
    siglongjmp(g_jmp, sig);
}

static void install_signal_handlers()
{
    struct sigaction sa = {};
    sa.sa_sigaction = sig_handler;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGSEGV, &sa, nullptr);
    sigaction(SIGBUS, &sa, nullptr);
    sigaction(SIGILL, &sa, nullptr);
}

static unsigned long long get_meminfo(const std::string &key)
{
    unsigned long long val = 0;
    char buf[256];
    FILE *f = fopen("/proc/meminfo", "r");
    if (!f) return 0;
    while (fgets(buf, sizeof(buf), f)) {
        if (strncmp(buf, key.c_str(), key.size()) == 0) {
            sscanf(buf, "%*s %llu", &val);
            fclose(f);
            return val * 1024;
        }
    }
    fclose(f);
    return 0;
}

static std::vector<mem_range> parse_iomem_system_ram()
{
    std::vector<mem_range> ranges;
    char buf[512];
    FILE *f = fopen("/proc/iomem", "r");
    if (!f) {
        perror("open /proc/iomem");
        return ranges;
    }
    while (fgets(buf, sizeof(buf), f)) {
        if (!strstr(buf, "System RAM") && !strstr(buf, "Persistent Memory"))
            continue;
        unsigned long long start, end;
        if (sscanf(buf, "%llx-%llx", &start, &end) != 2)
            continue;
        ranges.push_back({start, end + 1});
    }
    fclose(f);
    return ranges;
}

static bool read_probe(void *map, unsigned long long addr, scan_stats &st)
{
    int sig = sigsetjmp(g_jmp, 1);
    if (sig != 0) {
        st.faults++;
        std::printf("  [FAULT] %s at 0x%012llx (sig addr 0x%lx)\n",
                    sig_name(sig), addr, (unsigned long)g_fault_addr);
        return false;
    }

    volatile auto *p = static_cast<volatile unsigned long long *>(map);
    unsigned long long dummy = 0;
    for (int i = 0; i < PAGE_SIZE / sizeof(*p); i++)
        dummy += p[i];
    (void)dummy;
    return true;
}

class fd_guard {
    int fd_;
public:
    explicit fd_guard(int fd) : fd_(fd) {}
    ~fd_guard() { if (fd_ >= 0) close(fd_); }
    int get() const { return fd_; }
    operator int() const { return fd_; }
};

class mmap_guard {
    void  *ptr_;
    size_t len_;
public:
    mmap_guard(void *p, size_t len) : ptr_(p), len_(len) {}
    ~mmap_guard() { if (ptr_ != MAP_FAILED) munmap(ptr_, len_); }
    void *get() const { return ptr_; }
};

static void scan_physical_range(int fd, unsigned long long start,
                                unsigned long long end, scan_stats &st)
{
    for (unsigned long long addr = start; addr < end; addr += PAGE_SIZE) {
        mmap_guard mem(mmap(nullptr, PAGE_SIZE, PROT_READ, MAP_SHARED,
                            fd, static_cast<off_t>(addr)), PAGE_SIZE);
        if (mem.get() == MAP_FAILED) {
            std::printf("  [MMAP-FAIL] 0x%012llx: %s\n", addr, strerror(errno));
            st.skipped++;
            continue;
        }

        read_probe(mem.get(), addr, st);
        st.pages++;

        if (st.pages % 0x10000 == 0) {
            std::printf("  ... %llu pages (%llu MB), %llu faults      \r",
                        st.pages, st.pages * PAGE_SIZE >> 20, st.faults);
            std::fflush(stdout);
        }
    }
}

static void scan_physical(const std::vector<mem_range> &ranges, scan_stats &st)
{
    std::printf("\n=== Physical RAM scan via /dev/mem ===\n");

    fd_guard fd(open("/dev/mem", O_RDONLY | O_SYNC));
    if (fd.get() < 0) {
        std::printf("Cannot open /dev/mem: %s\n", strerror(errno));
        return;
    }

    for (size_t i = 0; i < ranges.size(); i++) {
        auto size = ranges[i].end - ranges[i].start;
        std::printf("\n  Range %zu: [0x%012llx - 0x%012llx) (%llu MB)\n",
                    i, ranges[i].start, ranges[i].end, size >> 20);
        scan_physical_range(fd, ranges[i].start, ranges[i].end, st);
    }
}

static void scan_virtual(unsigned long long size, scan_stats &st)
{
    std::printf("\n=== Virtual memory scan (%llu MB) via mmap ===\n", size >> 20);

    const unsigned long long chunk = 256ULL << 20;
    unsigned long long allocated = 0;

    while (allocated < size) {
        unsigned long long this_chunk = std::min(chunk, size - allocated);

        mmap_guard mem(mmap(nullptr, this_chunk, PROT_READ,
                            MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE, -1, 0),
                       this_chunk);
        if (mem.get() == MAP_FAILED) {
            std::printf("  mmap %llu MB failed: %s\n", this_chunk >> 20,
                        strerror(errno));
            break;
        }

        unsigned long long npages = this_chunk / PAGE_SIZE;
        for (unsigned long long i = 0; i < npages; i++) {
            void *page = static_cast<char *>(mem.get()) + i * PAGE_SIZE;
            read_probe(page, allocated + i * PAGE_SIZE, st);
            st.pages++;
        }

        allocated += this_chunk;
        std::printf("  %llu / %llu MB tested, %llu faults      \r",
                    allocated >> 20, size >> 20, st.faults);
        std::fflush(stdout);
    }
    std::printf("\n");
}

static void usage(const char *prog)
{
    std::printf(
        "Usage: %s [options]\n"
        "  -p           Scan physical RAM via /dev/mem (root, uses /proc/iomem)\n"
        "  -v           Scan virtual memory via mmap (default)\n"
        "  -m <size>    Virtual memory size in MB (default MemAvailable)\n"
        "  -h           Help\n", prog);
}

int main(int argc, char **argv)
{
    bool do_phys = false, do_virt = false;
    unsigned long long virt_size = 0;
    int opt;

    while ((opt = getopt(argc, argv, "pvm:h")) != -1) {
        switch (opt) {
        case 'p': do_phys = true; break;
        case 'v': do_virt = true; break;
        case 'm': virt_size = strtoull(optarg, nullptr, 0) << 20; break;
        case 'h': usage(argv[0]); return 0;
        default:  usage(argv[0]); return 1;
        }
    }

    if (!do_phys && !do_virt)
        do_virt = true;

    install_signal_handlers();

    auto mb = [](unsigned long long bytes) { return bytes >> 20; };

    std::printf(
        "memscan (read-only) - memory access fault detector\n"
        "====================================================\n\n"
        "  MemTotal:     %llu MB\n"
        "  MemFree:      %llu MB\n"
        "  MemAvailable: %llu MB\n",
        mb(get_meminfo("MemTotal")),
        mb(get_meminfo("MemFree")),
        mb(get_meminfo("MemAvailable")));

    auto t0 = std::chrono::steady_clock::now();
    scan_stats st;

    if (do_phys) {
        auto ranges = parse_iomem_system_ram();
        if (ranges.empty()) {
            std::printf("\nNo System RAM ranges found in /proc/iomem\n");
        } else {
            unsigned long long total = 0;
            for (auto &r : ranges)
                total += r.end - r.start;
            std::printf("  Physical RAM: %zu ranges, %llu MB total\n",
                        ranges.size(), mb(total));
            scan_physical(ranges, st);
        }
    }

    if (do_virt) {
        if (!virt_size)
            virt_size = get_meminfo("MemAvailable") ?: 256ULL << 20;
        scan_virtual(virt_size, st);
    }

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();

    std::printf(
        "\n--- Results ---\n"
        "  Pages tested:  %llu (%llu MB)\n"
        "  Pages skipped: %llu\n"
        "  Faults:        %llu\n"
        "  Time:          %.2f s\n"
        "  Result:        %s\n",
        st.pages, mb(st.pages * PAGE_SIZE),
        st.skipped, st.faults, elapsed,
        st.faults ? "FAIL" : "PASS");

    return st.faults ? 1 : 0;
}
