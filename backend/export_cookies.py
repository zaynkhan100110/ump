# backend/export_cookies.py
import browser_cookie3
import os

def export_bilibili_cookies():
    # Try Chrome first, then Firefox
    cookies = browser_cookie3.chrome(domain_name='bilibili.com')
    if not cookies:
        cookies = browser_cookie3.firefox(domain_name='bilibili.com')
    if not cookies:
        print("No cookies found for bilibili.com. Make sure you are logged in.")
        return

    with open('cookies.txt', 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        for cookie in cookies:
            f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t{bool(cookie.secure)}\t{int(cookie.expires) if cookie.expires else 0}\t{cookie.name}\t{cookie.value}\n")
    print("Cookies exported to cookies.txt")

if __name__ == "__main__":
    export_bilibili_cookies()