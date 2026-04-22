#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <setjmp.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <stdarg.h>
#include <time.h>

#ifndef PAGE_SIZE
#define PAGE_SIZE       4096
#endif

#ifndef MAP_POPULATE
#define MAP_POPULATE    0x008000
#endif

#define MAX_RANGES      256

struct mem_range {
        unsigned long long start;
        unsigned long long end;
};

static sigjmp_buf            jump_buf;
static volatile sig_atomic_t fault_addr;
static unsigned long long    total_pages;
static unsigned long long    total_faults;
static unsigned long long    total_skipped;

static void sig_handler(int sig, siginfo_t *si, void *ctx)
{
        fault_addr = (sig_atomic_t)(unsigned long)si->si_addr;
        siglongjmp(jump_buf, sig);
}

static void install_signal_handlers(void)
{
        struct sigaction sa = {};
        sa.sa_sigaction = sig_handler;
        sa.sa_flags = SA_SIGINFO;
        sigaction(SIGSEGV, &sa, NULL);
        sigaction(SIGBUS, &sa, NULL);
        sigaction(SIGILL, &sa, NULL);
}

static const char *sig_name(int sig)
{
        switch (sig) {
        case SIGSEGV: return "SIGSEGV";
        case SIGBUS:  return "SIGBUS";
        case SIGILL:  return "SIGILL";
        default:      return "UNKNOWN";
        }
}

static unsigned long long get_meminfo(const char *key)
{
        char buf[256];
        unsigned long long val = 0;
        FILE *f = fopen("/proc/meminfo", "r");
        if (!f) return 0;
        while (fgets(buf, sizeof(buf), f)) {
                if (strncmp(buf, key, strlen(key)) == 0) {
                        sscanf(buf, "%*s %llu", &val);
                        fclose(f);
                        return val * 1024;
                }
        }
        fclose(f);
        return 0;
}

static int parse_iomem_system_ram(struct mem_range *ranges, int max_ranges)
{
        FILE *f;
        char buf[512];
        int count = 0;

        f = fopen("/proc/iomem", "r");
        if (!f) {
                perror("open /proc/iomem");
                return 0;
        }

        while (fgets(buf, sizeof(buf), f)) {
                unsigned long long start, end;
                if (strstr(buf, "System RAM") == NULL &&
                    strstr(buf, "Persistent Memory") == NULL)
                        continue;
                if (sscanf(buf, "%llx-%llx", &start, &end) != 2)
                        continue;
                ranges[count].start = start;
                ranges[count].end = end + 1;
                if (++count >= max_ranges)
                        break;
        }

        fclose(f);
        return count;
}

static int read_probe(void *map, unsigned long long phys_addr)
{
        int sig = sigsetjmp(jump_buf, 1);
        if (sig != 0) {
                total_faults++;
                printf("  [FAULT] %s at 0x%012llx (sig addr 0x%lx)\n",
                       sig_name(sig), phys_addr, (unsigned long)fault_addr);
                return -1;
        }

        volatile unsigned long long *p = (volatile unsigned long long *)map;
        unsigned long long dummy = 0;
        int i;

        for (i = 0; i < PAGE_SIZE / sizeof(*p); i++)
                dummy += p[i];

        (void)dummy;
        return 0;
}

static void scan_physical_range(int fd, unsigned long long start,
                                unsigned long long end)
{
        unsigned long long addr;

        for (addr = start; addr < end; addr += PAGE_SIZE) {
                void *map = mmap(NULL, PAGE_SIZE, PROT_READ, MAP_SHARED,
                                 fd, (off_t)addr);
                if (map == MAP_FAILED) {
                        printf("  [MMAP-FAIL] 0x%012llx: %s\n",
                               addr, strerror(errno));
                        total_skipped++;
                        continue;
                }

                read_probe(map, addr);
                total_pages++;
                munmap(map, PAGE_SIZE);

                if (total_pages % 0x10000 == 0) {
                        printf("  ... %llu pages (%llu MB), %llu faults      \r",
                               total_pages, total_pages * PAGE_SIZE >> 20,
                               total_faults);
                        fflush(stdout);
                }
        }
}

static void scan_physical(const struct mem_range *ranges, int nranges)
{
        int fd, i;

        printf("\n=== Physical RAM scan via /dev/mem ===\n");

        fd = open("/dev/mem", O_RDONLY | O_SYNC);
        if (fd < 0) {
                printf("Cannot open /dev/mem: %s\n", strerror(errno));
                return;
        }

        for (i = 0; i < nranges; i++) {
                unsigned long long size = ranges[i].end - ranges[i].start;
                printf("\n  Range %d: [0x%012llx - 0x%012llx) (%llu MB)\n",
                       i, ranges[i].start, ranges[i].end, size >> 20);
                scan_physical_range(fd, ranges[i].start, ranges[i].end);
        }

        close(fd);
}

static void scan_virtual(unsigned long long size)
{
        printf("\n=== Virtual memory scan (%llu MB) via mmap ===\n", size >> 20);

        unsigned long long allocated = 0;
        unsigned long long chunk = 256ULL << 20;

        while (allocated < size) {
                unsigned long long this = chunk;
                if (this > size - allocated)
                        this = size - allocated;

                void *region = mmap(NULL, this, PROT_READ,
                                    MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE,
                                    -1, 0);
                if (region == MAP_FAILED) {
                        printf("  mmap %llu MB failed: %s\n", this >> 20,
                               strerror(errno));
                        break;
                }

                unsigned long long npages = this / PAGE_SIZE;
                unsigned long long i;
                for (i = 0; i < npages; i++) {
                        void *page = (char *)region + i * PAGE_SIZE;
                        read_probe(page, allocated + i * PAGE_SIZE);
                        total_pages++;
                }

                munmap(region, this);
                allocated += this;

                printf("  %llu / %llu MB tested, %llu faults      \r",
                       allocated >> 20, size >> 20, total_faults);
                fflush(stdout);
        }
        printf("\n");
}

static void usage(const char *prog)
{
        printf("Usage: %s [options]\n"
               "  -p           Scan physical RAM via /dev/mem (root, uses /proc/iomem)\n"
               "  -v           Scan virtual memory via mmap (default)\n"
               "  -m <size>    Virtual memory size in MB (default MemAvailable)\n"
               "  -h           Help\n",
               prog);
}

int main(int argc, char **argv)
{
        int do_phys = 0, do_virt = 0;
        unsigned long long virt_size = 0;
        struct timespec t0, t1;

        while (1) {
                int opt = getopt(argc, argv, "pvm:h");
                if (opt == -1) break;
                switch (opt) {
                case 'p': do_phys = 1; break;
                case 'v': do_virt = 1; break;
                case 'm': virt_size = strtoull(optarg, NULL, 0) << 20; break;
                case 'h': usage(argv[0]); return 0;
                default:  usage(argv[0]); return 1;
                }
        }

        if (!do_phys && !do_virt)
                do_virt = 1;

        install_signal_handlers();

        printf("memscan (read-only) - memory access fault detector\n"
               "====================================================\n\n"
               "  MemTotal:     %llu MB\n"
               "  MemFree:      %llu MB\n"
               "  MemAvailable: %llu MB\n",
               get_meminfo("MemTotal") >> 20,
               get_meminfo("MemFree") >> 20,
               get_meminfo("MemAvailable") >> 20);

        clock_gettime(CLOCK_MONOTONIC, &t0);

        if (do_phys) {
                struct mem_range ranges[MAX_RANGES];
                int nranges = parse_iomem_system_ram(ranges, MAX_RANGES);
                if (nranges == 0) {
                        printf("\nNo System RAM ranges found in /proc/iomem\n");
                } else {
                        unsigned long long total = 0;
                        int i;
                        for (i = 0; i < nranges; i++)
                                total += ranges[i].end - ranges[i].start;
                        printf("  Physical RAM: %d ranges, %llu MB total\n",
                               nranges, total >> 20);
                        scan_physical(ranges, nranges);
                }
        }

        if (do_virt) {
                if (!virt_size)
                        virt_size = get_meminfo("MemAvailable") ?: 256ULL << 20;
                scan_virtual(virt_size);
        }

        clock_gettime(CLOCK_MONOTONIC, &t1);
        double elapsed = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;

        printf("\n--- Results ---\n"
               "  Pages tested:  %llu (%llu MB)\n"
               "  Pages skipped: %llu\n"
               "  Faults:        %llu\n"
               "  Time:          %.2f s\n"
               "  Result:        %s\n",
               total_pages, total_pages * PAGE_SIZE >> 20,
               total_skipped, total_faults, elapsed,
               total_faults ? "FAIL" : "PASS");

        return total_faults ? 1 : 0;
}
