import os
import subprocess
import threading


# stderr 最大收集字符数（约 1M 字符），防止大文件转码时日志撑爆内存
_MAX_STDERR_CHARS = 1024 * 1024


def windows_subprocess_kwargs():
    """返回 Windows 平台下隐藏子进程窗口所需的额外参数。"""
    kwargs = {}
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _drain_pipe(pipe, result_list, max_chars=None):
    """
    在后台线程中持续读取管道数据，防止管道缓冲区满导致子进程死锁。

    这是解决 subprocess PIPE 死锁的标准方案——communicate() 内部也是
    用线程并发读取的。我们用独立函数是为了能在主线程中轮询取消标志。
    """
    try:
        if max_chars is not None:
            data = pipe.read(max_chars)
        else:
            data = pipe.read()
        result_list.append(data or "")
    except Exception:
        result_list.append("")


def run_command(cmd, cancelled_flag=lambda: False):
    """
    执行外部命令，支持取消标志轮询。

    设计要点：
    1. 用后台线程持续排空 stdout/stderr 管道，防止子进程因管道满而阻塞（死锁）。
    2. 主线程轮询 cancelled_flag，取消时立即 terminate 子进程。
    3. 限制 stderr 收集量，防止长时间转码的 ffmpeg 日志撑爆内存。
    4. 确保管道在所有路径上都被正确关闭，防止资源泄漏。
    """
    if cancelled_flag():
        return False, "cancelled", ""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            **windows_subprocess_kwargs(),
        )
    except FileNotFoundError as e:
        return False, str(e), ""
    except Exception as e:
        return False, str(e), ""

    # 启动后台线程持续读取管道，防止缓冲区满导致死锁
    # （这是 communicate() 内部的实现原理，我们拆出来以便同时轮询取消标志）
    stdout_result = []
    stderr_result = []
    stdout_thread = threading.Thread(
        target=_drain_pipe, args=(proc.stdout, stdout_result), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_drain_pipe, args=(proc.stderr, stderr_result, _MAX_STDERR_CHARS), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    try:
        # 轮询等待子进程结束，同时检查取消标志
        while proc.poll() is None:
            if cancelled_flag():
                # 先温和终止，超时后强制杀死
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                # 进程已死，管道会 EOF，等读取线程自然退出
                stdout_thread.join(timeout=3)
                stderr_thread.join(timeout=3)
                return False, "cancelled", ""
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass

        # 子进程已结束，等待读取线程完成
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)

        stdout = stdout_result[0] if stdout_result else ""
        stderr_raw = stderr_result[0] if stderr_result else ""
    finally:
        # 确保管道被关闭，防止文件描述符泄漏
        try:
            proc.stdout.close()
        except Exception:
            pass
        try:
            proc.stderr.close()
        except Exception:
            pass

    if proc.returncode != 0:
        return False, stderr_raw.strip()[-1000:], stdout
    return True, "", stdout
