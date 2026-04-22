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

static sigjmp_buf            jump_buf;
static volatile sig_atomic_t fault_addr;
static unsigned long long    total_pages;
static unsigned long long    total_faults;

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

static void scan_physical(unsigned long long start, unsigned long long end)
{
        int fd;

        printf("\n=== Physical memory scan [0x%llx - 0x%llx] via /dev/mem ===\n",
               start, end);

        fd = open("/dev/mem", O_RDONLY | O_SYNC);
        if (fd < 0) {
                printf("Cannot open /dev/mem: %s (need root)\n", strerror(errno));
                return;
        }

        unsigned long long addr;
        for (addr = start; addr < end; addr += PAGE_SIZE) {
                void *map = mmap(NULL, PAGE_SIZE, PROT_READ, MAP_SHARED,
                                 fd, (off_t)addr);
                if (map == MAP_FAILED) {
                        printf("  [MMAP-FAIL] 0x%012llx: %s\n", addr, strerror(errno));
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
               "  -p           Scan physical memory via /dev/mem (root)\n"
               "  -v           Scan virtual memory via mmap (default)\n"
               "  -s <addr>    Physical start address (default 0)\n"
               "  -e <addr>    Physical end address (default MemTotal)\n"
               "  -m <size>    Virtual memory size in MB (default MemAvailable)\n"
               "  -h           Help\n",
               prog);
}

int main(int argc, char **argv)
{
        int do_phys = 0, do_virt = 0;
        unsigned long long phys_start = 0, phys_end = 0, virt_size = 0;
        struct timespec t0, t1;

        while (1) {
                int opt = getopt(argc, argv, "pvs:e:m:h");
                if (opt == -1) break;
                switch (opt) {
                case 'p': do_phys = 1; break;
                case 'v': do_virt = 1; break;
                case 's': phys_start = strtoull(optarg, NULL, 0); break;
                case 'e': phys_end = strtoull(optarg, NULL, 0); break;
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
                if (!phys_end)
                        phys_end = get_meminfo("MemTotal") ?: 0x40000000ULL;
                scan_physical(phys_start, phys_end);
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
               "  Faults:        %llu\n"
               "  Time:          %.2f s\n"
               "  Result:        %s\n",
               total_pages, total_pages * PAGE_SIZE >> 20,
               total_faults, elapsed,
               total_faults ? "FAIL" : "PASS");

        return total_faults ? 1 : 0;
}
