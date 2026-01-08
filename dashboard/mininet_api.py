import subprocess

def run_cmd(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.stdout

def run_on_host(host, command):
    """
    Esegue un comando su un host Mininet (h1, h2, ...)
    """
    return run_cmd(f"sudo mnexec -a {host} {command}")
