#define _XOPEN_SOURCE 700
#include <sys/types.h>
#include <sys/stat.h>
#include <syslog.h>
#include <signal.h>
#include <dirent.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <openssl/sha.h>
#include <sys/wait.h>
#include <time.h>
#include <stdarg.h>

#define DEFAULT_SLEEP_SECONDS 300
#define SHA256_HEX_LEN 64
#define MAX_ERRORS 32

static volatile sig_atomic_t wake_requested = 0;
static volatile sig_atomic_t dump_requested = 0;
static volatile sig_atomic_t terminate_requested = 0;

struct file_state {
    char *path;
    off_t size;
    time_t mtime;
    char checksum[SHA256_HEX_LEN + 1];
    int seen;
    struct file_state *next;
};

struct daemon_config {
    char watch_dir[PATH_MAX];
    unsigned int sleep_seconds;
    int recursive;
    char django_python[PATH_MAX];
    char django_manage[PATH_MAX];
    char django_username[128];
    char archive_ok[PATH_MAX];
    char archive_error[PATH_MAX];
    char module[16];
    char status_dir[PATH_MAX];
    int foreground;
};

static struct daemon_config g_cfg;
static struct file_state *g_head = NULL;
static int mkdir_if_missing(const char *path);

static void on_sigusr1(int sig) { (void)sig; wake_requested = 1; }
static void on_sigusr2(int sig) { (void)sig; dump_requested = 1; }
static void on_sigterm(int sig) { (void)sig; terminate_requested = 1; }


static void iso_now(char *out, size_t out_size) {
    time_t now = time(NULL);
    struct tm tm_now;
    localtime_r(&now, &tm_now);
    strftime(out, out_size, "%Y-%m-%dT%H:%M:%S", &tm_now);
}

static void write_status_file(const char *phase, const char *last_file, int last_rc, const char *last_error) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/import_watchd_%s.json", g_cfg.status_dir[0] ? g_cfg.status_dir : "/tmp", g_cfg.module);
    mkdir_if_missing(g_cfg.status_dir[0] ? g_cfg.status_dir : "/tmp");
    FILE *fp = fopen(path, "w");
    if (!fp) return;
    char now_iso[32];
    iso_now(now_iso, sizeof(now_iso));
    fprintf(fp,
        "{\n"
        "  \"module\": \"%s\",\n"
        "  \"pid\": %ld,\n"
        "  \"watch_dir\": \"%s\",\n"
        "  \"sleep_seconds\": %u,\n"
        "  \"recursive\": %s,\n"
        "  \"phase\": \"%s\",\n"
        "  \"last_seen\": \"%s\",\n"
        "  \"last_file\": \"%s\",\n"
        "  \"last_rc\": %d,\n"
        "  \"running\": %s,\n"
        "  \"last_error\": \"%s\"\n"
        "}\n",
        g_cfg.module,
        (long)getpid(),
        g_cfg.watch_dir,
        g_cfg.sleep_seconds,
        g_cfg.recursive ? "true" : "false",
        phase ? phase : "idle",
        now_iso,
        last_file ? last_file : "",
        last_rc,
        terminate_requested ? "false" : "true",
        last_error ? last_error : ""
    );
    fclose(fp);
}

static void free_states(struct file_state *head) {
    while (head) {
        struct file_state *next = head->next;
        free(head->path);
        free(head);
        head = next;
    }
}

static struct file_state *find_state(const char *path) {
    struct file_state *curr = g_head;
    while (curr) {
        if (strcmp(curr->path, path) == 0) return curr;
        curr = curr->next;
    }
    return NULL;
}

static int sha256_file(const char *path, char out_hex[SHA256_HEX_LEN + 1], off_t *size_out, time_t *mtime_out) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;

    struct stat st;
    if (fstat(fd, &st) != 0) {
        close(fd);
        return -1;
    }

    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256_CTX ctx;
    SHA256_Init(&ctx);

    unsigned char buf[8192];
    ssize_t n;
    while ((n = read(fd, buf, sizeof(buf))) > 0) {
        SHA256_Update(&ctx, buf, (size_t)n);
    }
    close(fd);
    if (n < 0) return -1;

    SHA256_Final(hash, &ctx);
    for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
        snprintf(out_hex + (i * 2), 3, "%02x", hash[i]);
    }
    out_hex[SHA256_HEX_LEN] = '\0';
    if (size_out) *size_out = st.st_size;
    if (mtime_out) *mtime_out = st.st_mtime;
    return 0;
}

static int mkdir_if_missing(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) {
        return S_ISDIR(st.st_mode) ? 0 : -1;
    }
    return mkdir(path, 0755);
}

static void ensure_archive_dirs(void) {
    if (g_cfg.archive_ok[0]) mkdir_if_missing(g_cfg.archive_ok);
    if (g_cfg.archive_error[0]) mkdir_if_missing(g_cfg.archive_error);
}

static int move_to_archive(const char *src_path, int success) {
    const char *dst_dir = success ? g_cfg.archive_ok : g_cfg.archive_error;
    if (!dst_dir[0]) return 0;

    const char *base = strrchr(src_path, '/');
    base = base ? base + 1 : src_path;
    char dst[PATH_MAX];
    time_t now = time(NULL);
    snprintf(dst, sizeof(dst), "%s/%ld_%s", dst_dir, (long)now, base);
    if (rename(src_path, dst) != 0) {
        syslog(LOG_ERR, "Nie udało się przenieść pliku %s do archiwum %s: %s", src_path, dst, strerror(errno));
        return -1;
    }
    syslog(LOG_INFO, "Przeniesiono plik %s do %s", src_path, dst);
    return 0;
}

static const char *management_command_for_module(void) {
    if (strcmp(g_cfg.module, "dom") == 0) return "importuj_domowy_plik_watchera";
    return "importuj_plik_watchera";
}

static int run_django_import(const char *path) {
    pid_t pid = fork();
    if (pid < 0) {
        syslog(LOG_ERR, "fork() nieudany dla importu %s: %s", path, strerror(errno));
        return -1;
    }
    if (pid == 0) {
        execl(
            g_cfg.django_python,
            g_cfg.django_python,
            g_cfg.django_manage,
            management_command_for_module(),
            "--username", g_cfg.django_username,
            "--path", path,
            (char *)NULL
        );
        _exit(127);
    }

    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        syslog(LOG_ERR, "waitpid() nieudany dla %s: %s", path, strerror(errno));
        return -1;
    }

    if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
        syslog(LOG_INFO, "Import Django zakończony powodzeniem dla %s", path);
        return 0;
    }
    if (WIFEXITED(status)) {
        syslog(LOG_ERR, "Import Django zakończony kodem %d dla %s", WEXITSTATUS(status), path);
    } else if (WIFSIGNALED(status)) {
        syslog(LOG_ERR, "Import Django ubity sygnałem %d dla %s", WTERMSIG(status), path);
    }
    return -1;
}

static void dump_states(void) {
    struct file_state *curr = g_head;
    syslog(LOG_INFO, "SIGUSR2: wypisywanie stanu obserwowanych plików");
    while (curr) {
        syslog(LOG_INFO, "plik=%s size=%ld mtime=%ld sha256=%s", curr->path, (long)curr->size, (long)curr->mtime, curr->checksum);
        curr = curr->next;
    }
}

static int is_regular_file_no_symlink(const char *path, const struct stat *st) {
    (void)path;
    return S_ISREG(st->st_mode);
}

static int should_import(const char *path) {
    const char *ext = strrchr(path, '.');
    if (!ext) return 0;
    if (strcmp(g_cfg.module, "dom") == 0) {
        return strcmp(ext, ".csv") == 0;
    }
    return strcmp(ext, ".xlsx") == 0 || strcmp(ext, ".xlsm") == 0;
}

static void upsert_state(const char *path, off_t size, time_t mtime, const char *checksum, int was_new) {
    struct file_state *curr = find_state(path);
    if (!curr) {
        curr = calloc(1, sizeof(*curr));
        curr->path = strdup(path);
        curr->next = g_head;
        g_head = curr;
        if (was_new) {
            syslog(LOG_INFO, "Nowy plik: %s size=%ld mtime=%ld sha256=%s", path, (long)size, (long)mtime, checksum);
        }
    } else {
        if (strcmp(curr->checksum, checksum) != 0 || curr->size != size || curr->mtime != mtime) {
            syslog(LOG_INFO, "Zmiana pliku: %s old(size=%ld mtime=%ld sha256=%s) new(size=%ld mtime=%ld sha256=%s)",
                path, (long)curr->size, (long)curr->mtime, curr->checksum, (long)size, (long)mtime, checksum);
        }
    }
    curr->size = size;
    curr->mtime = mtime;
    strncpy(curr->checksum, checksum, sizeof(curr->checksum) - 1);
    curr->checksum[sizeof(curr->checksum) - 1] = '\0';
    curr->seen = 1;
}

static void clear_seen_flags(void) {
    struct file_state *curr = g_head;
    while (curr) {
        curr->seen = 0;
        curr = curr->next;
    }
}

static void purge_missing_files(void) {
    struct file_state **pp = &g_head;
    while (*pp) {
        if (!(*pp)->seen) {
            struct file_state *missing = *pp;
            syslog(LOG_INFO, "Plik zniknął: %s", missing->path);
            *pp = missing->next;
            free(missing->path);
            free(missing);
        } else {
            pp = &(*pp)->next;
        }
    }
}

static int scan_dir_recursive(const char *dir_path, int initial_scan) {
    DIR *dir = opendir(dir_path);
    if (!dir) {
        syslog(LOG_ERR, "Nie można otworzyć katalogu %s: %s", dir_path, strerror(errno));
        return -1;
    }

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;

        char path[PATH_MAX];
        snprintf(path, sizeof(path), "%s/%s", dir_path, entry->d_name);

        struct stat st;
        if (lstat(path, &st) != 0) {
            syslog(LOG_WARNING, "lstat nieudany dla %s: %s", path, strerror(errno));
            continue;
        }

        if (S_ISLNK(st.st_mode)) {
            continue;
        }
        if (S_ISDIR(st.st_mode)) {
            if (g_cfg.recursive) {
                scan_dir_recursive(path, initial_scan);
            }
            continue;
        }
        if (!is_regular_file_no_symlink(path, &st)) {
            continue;
        }

        char checksum[SHA256_HEX_LEN + 1];
        off_t size = 0;
        time_t mtime = 0;
        if (sha256_file(path, checksum, &size, &mtime) != 0) {
            syslog(LOG_WARNING, "Nie udało się policzyć SHA-256 dla %s: %s", path, strerror(errno));
            continue;
        }

        struct file_state *existing = find_state(path);
        int is_new = existing == NULL;
        upsert_state(path, size, mtime, checksum, is_new);

        if (!initial_scan && is_new && should_import(path)) {
            write_status_file("importing", path, 0, "");
            int rc = run_django_import(path);
            write_status_file(rc == 0 ? "import_ok" : "import_error", path, rc, rc == 0 ? "" : "Import Django zwrócił błąd");
            move_to_archive(path, rc == 0);
        }
    }

    closedir(dir);
    return 0;
}

static int daemonize_process(void) {
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (pid > 0) exit(EXIT_SUCCESS);

    if (setsid() < 0) return -1;

    signal(SIGHUP, SIG_IGN);
    pid = fork();
    if (pid < 0) return -1;
    if (pid > 0) exit(EXIT_SUCCESS);

    umask(0);
    if (chdir("/") != 0) return -1;

    int fd = open("/dev/null", O_RDWR);
    if (fd >= 0) {
        dup2(fd, STDIN_FILENO);
        dup2(fd, STDOUT_FILENO);
        dup2(fd, STDERR_FILENO);
        if (fd > 2) close(fd);
    }
    return 0;
}

static int parse_args(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr, "Użycie: %s <katalog> <python> <manage.py> <username> [--module dom|firma] [--status-dir dir] [-t sekundy] [-R] [--archive-ok dir] [--archive-error dir] [--foreground]\n", argv[0]);
        return -1;
    }

    memset(&g_cfg, 0, sizeof(g_cfg));
    realpath(argv[1], g_cfg.watch_dir);
    realpath(argv[2], g_cfg.django_python);
    realpath(argv[3], g_cfg.django_manage);
    strncpy(g_cfg.django_username, argv[4], sizeof(g_cfg.django_username) - 1);
    g_cfg.sleep_seconds = DEFAULT_SLEEP_SECONDS;
    strncpy(g_cfg.module, "firma", sizeof(g_cfg.module) - 1);
    strncpy(g_cfg.status_dir, "/tmp", sizeof(g_cfg.status_dir) - 1);

    for (int i = 5; i < argc; i++) {
        if (strcmp(argv[i], "--module") == 0 && i + 1 < argc) {
            strncpy(g_cfg.module, argv[++i], sizeof(g_cfg.module) - 1);
        } else if (strcmp(argv[i], "--status-dir") == 0 && i + 1 < argc) {
            strncpy(g_cfg.status_dir, argv[++i], sizeof(g_cfg.status_dir) - 1);
        } else if (strcmp(argv[i], "-R") == 0) {
            g_cfg.recursive = 1;
        } else if (strcmp(argv[i], "-t") == 0 && i + 1 < argc) {
            g_cfg.sleep_seconds = (unsigned int)strtoul(argv[++i], NULL, 10);
        } else if (strcmp(argv[i], "--archive-ok") == 0 && i + 1 < argc) {
            strncpy(g_cfg.archive_ok, argv[++i], sizeof(g_cfg.archive_ok) - 1);
        } else if (strcmp(argv[i], "--archive-error") == 0 && i + 1 < argc) {
            strncpy(g_cfg.archive_error, argv[++i], sizeof(g_cfg.archive_error) - 1);
        } else if (strcmp(argv[i], "--foreground") == 0) {
            g_cfg.foreground = 1;
        } else {
            fprintf(stderr, "Nieznany argument: %s\n", argv[i]);
            return -1;
        }
    }

    struct stat st;
    if (strcmp(g_cfg.module, "dom") != 0 && strcmp(g_cfg.module, "firma") != 0) {
        fprintf(stderr, "Błąd: --module musi mieć wartość dom albo firma\n");
        return -1;
    }

    if (stat(g_cfg.watch_dir, &st) != 0 || !S_ISDIR(st.st_mode)) {
        fprintf(stderr, "Błąd: %s nie jest katalogiem\n", argv[1]);
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (parse_args(argc, argv) != 0) {
        return EXIT_FAILURE;
    }

    if (!g_cfg.foreground && daemonize_process() != 0) {
        perror("daemonize_process");
        return EXIT_FAILURE;
    }

    openlog("import_watchd", LOG_PID | LOG_NDELAY, LOG_DAEMON);
    ensure_archive_dirs();

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_sigusr1;
    sigaction(SIGUSR1, &sa, NULL);
    sa.sa_handler = on_sigusr2;
    sigaction(SIGUSR2, &sa, NULL);
    sa.sa_handler = on_sigterm;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    syslog(LOG_INFO, "Start demona. modul=%s katalog=%s sleep=%u recursive=%d foreground=%d", g_cfg.module, g_cfg.watch_dir, g_cfg.sleep_seconds, g_cfg.recursive, g_cfg.foreground);
    write_status_file("starting", "", 0, "");
    clear_seen_flags();
    scan_dir_recursive(g_cfg.watch_dir, 1);
    purge_missing_files();

    while (!terminate_requested) {
        syslog(LOG_INFO, "Demon usypia na %u sekund", g_cfg.sleep_seconds);
        unsigned int remaining = g_cfg.sleep_seconds;
        while (remaining > 0 && !wake_requested && !dump_requested && !terminate_requested) {
            remaining = sleep(remaining);
        }

        if (terminate_requested) break;
        if (dump_requested) {
            dump_requested = 0;
            dump_states();
        }

        if (wake_requested) {
            syslog(LOG_INFO, "Demon obudzony sygnałem SIGUSR1");
            wake_requested = 0;
        } else {
            syslog(LOG_INFO, "Demon obudzony naturalnie po czasie snu");
        }

        write_status_file("scanning", "", 0, "");
        clear_seen_flags();
        scan_dir_recursive(g_cfg.watch_dir, 0);
        purge_missing_files();
        write_status_file("sleeping", "", 0, "");
    }

    syslog(LOG_INFO, "Kończenie pracy demona");
    write_status_file("stopped", "", 0, "");
    free_states(g_head);
    closelog();
    return EXIT_SUCCESS;
}
