## Dependencies

NeonFoundry depends on several Linux system libraries and utilities to provide its enhanced partition and mount management features:

| Dependency        | Purpose                                                                                 |
|-------------------|----------------------------------------------------------------------------------------|
| **glibc (C stdlib)**          | Base C library required for all C programs (stdio, stdlib, string, etc.)      |
| **unistd.h**      | Provides POSIX operating system API (file, process, terminal management)                |
| **dirent.h**      | Directory traversal and listing                                                         |
| **sys/stat.h**    | File and directory attributes, permissions                                              |
| **sys/mount.h**   | Mount and unmount filesystems                                                           |
| **sys/sysmacros.h** | Major/minor device macros                                                             |
| **fcntl.h**       | File and device control operations                                                      |
| **errno.h**       | Error handling                                                                          |
| **termios.h**     | Terminal control, raw mode input                                                        |
| **ctype.h**       | Character-type operations                                                               |
| **time.h**        | Time and date management                                                                |
| **signal.h**      | Signal handling (e.g., SIGINT)                                                          |
| **linux/fs.h**    | Filesystem-specific operations                                                          |
| **sys/ioctl.h**   | Device I/O control                                                                      |
| **lsblk**         | Lists block devices and partitions (used for partition detection)                       |
| **mount / umount**| Mount and unmount filesystems                                                           |
| **ntfs-3g**       | NTFS filesystem support (for mounting Windows partitions)                               |
| **fuser / lsof**  | Find and kill processes using a device or mountpoint                                    |
| **df**            | Disk usage reporting                                                                    |
| **swapoff / swapon** | Swap partition management                                                            |
| **sudo**          | Elevate privileges for system operations if required                                    |

**Why these dependencies?**  
NeonFoundry interacts directly with Linux system partitions and filesystems, requiring low-level access to system calls and utilities. It provides a terminal-based UI, colored output, and safety features (e.g., preventing unmount of root). Some features, like NTFS support, are optional and auto-detected.

---

*Note: Most dependencies are standard on Linux systems. NTFS support (`ntfs-3g`) is recommended for handling Windows-formatted drives.*