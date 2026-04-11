import subprocess
import sys

MESSAGE = "You have been launched as a subprocess under python. Can you figure out your PID and your parent's PID. Print those out in a fancy message and exit."


def main():
    subprocess.run(["opencode", "run", MESSAGE])


if __name__ == "__main__":
    main()
