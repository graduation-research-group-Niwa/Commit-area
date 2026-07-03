# パケットアナライザ（プロトコル学習支援ツール）

自作のパケットキャプチャ・解析ツール。Ethernet / IP / TCP / UDP の各層を
自前でデコードし、初学者向けの解説付きで表示する。

## ファイル構成

```
packet-analyzer/
├── main.py           # エントリーポイント（これを実行する）
├── gui.py            # Tkinter GUI
├── analyzer.py        # パケットキャプチャ・解析エンジン（GUI非依存）
├── explanations.py    # 学習支援用フィールド解説辞書
└── requirements.txt   # 依存ライブラリ
```

## セットアップ

```bash
pip3 install -r requirements.txt
sudo apt install python3-tk -y   # 未導入の場合
```

## 実行方法

```bash
sudo python3 main.py
```

パケットキャプチャには管理者権限が必要なため、`sudo` をつけて実行すること。

WSL2環境でPermissionErrorが出る場合は `.wslconfig` の設定
（`kernelCommandLine = apparmor=0`）を先に行うこと。

## 動作確認（GUIなし）

キャプチャエンジン単体の動作確認をしたい場合:

```bash
sudo python3 analyzer.py
```

5秒間キャプチャして結果をコンソールに出力する。

## 現在の実装範囲（Phase 2 相当）

- [x] Ethernet / IP / TCP / UDP のデコード
- [x] リアルタイムキャプチャ・一覧表示
- [x] パケット詳細表示（フィールド解説つき）
- [x] IPアドレス・ポート番号によるフィルタリング
- [x] プロトコル割合の円グラフ
- [x] pcapファイルの保存・読み込み（Wireshark互換）

## 未実装（Phase 3以降で追加予定）

- [ ] TCPハンドシェイク可視化
- [ ] 簡易異常検知アラート
- [ ] DNS解析・ドメイン名逆引き
- [ ] プロトコルフィールドのクイズ機能
- [ ] PyInstallerによるexe化
