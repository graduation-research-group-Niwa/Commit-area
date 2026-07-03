"""
main.py
アプリケーションのエントリーポイント

実行方法:
    sudo python3 main.py

    ※ パケットキャプチャにはroot権限が必要です。
"""

from gui import App

if __name__ == "__main__":
    app = App()
    app.mainloop()
