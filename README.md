# **プログラムの簡単に説明**
このプログラムは以下のことを実現します：
1. ドローン（Tello）をWi-Fi経由で接続。
2. ドローンのカメラ映像をリアルタイムで取得してPCに表示。
3. 映像の中で特定の色（デフォルトは赤色）を検出し、その色がどこにあるかを特定。
4. キーボードを使ってドローンを離陸、着陸、移動させる。

---

# **必要な知識**

## **ドローン（Tello）の基本動作**
- **Tello**は小型ドローンで、Wi-Fiを通じてスマホやPCから操作できます。
- Pythonライブラリ`djitellopy`を使うと、プログラムから簡単に動かせます。

## **HSV色空間とは？**
- **HSV**は、色を直感的に表すための方法で、以下の3つで表されます：
  - **H（Hue, 色相）**: 色そのもの（赤や青など）。
  - **S（Saturation, 彩度）**: 色の鮮やかさ。
  - **V（Value, 明度）**: 色の明るさ。

プログラムでは、特定の色をHSVで指定して検出しています。

---

# **プログラムの各部分の詳細解説**

---

## **ヘッダー部分**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
```
- `#!/usr/bin/env python3`:
  - スクリプトをPython 3で実行することを指定します。
- `# -*- coding: utf-8 -*-`:
  - スクリプトの文字コードをUTF-8に設定します。

---

## **ライブラリのインポート**
```python
from djitellopy import Tello, TelloException
import sys
import time
import cv2
from threading import Thread
from queue import Queue
import numpy as np
```

| ライブラリ      | 役割                                                                 |
|-----------------|----------------------------------------------------------------------|
| **djitellopy**  | Telloドローンを操作するためのライブラリ。                             |
| **sys**         | プログラムの終了処理で`sys.exit`を使用。                              |
| **time**        | 処理を一定時間停止するための`time.sleep`を使用。                      |
| **cv2**         | OpenCVを使って画像処理やカメラ映像を扱う。                             |
| **threading**   | `Thread`を使って並列処理を実現。                                      |
| **queue**       | キューを使って最新のカメラフレームを管理。                              |
| **numpy**       | 色の検出やラベリング処理（領域の面積計算など）に使用。                 |

---

## **TelloControlクラス**
このクラスはドローンを制御するすべての機能をまとめています。

---

### **`__init__`（初期化メソッド）**
```python
def __init__(self, ip, port):
    self.tello = Tello()
    self.tello.connect()
    self.tello.streamoff()
    self.tello.streamon()
```
- **`self.tello = Tello()`**:
  - Telloクラスのインスタンスを作成。
- **`self.tello.connect()`**:
  - Telloに接続（Wi-Fi経由）。
- **`self.tello.streamon()`**:
  - カメラ映像の転送を有効化。

---

### **カメラ映像の取得**
```python
self.cap = cv2.VideoCapture(f'udp://{ip}:{port}')
```
- **`cv2.VideoCapture`**:
  - カメラ映像を取得するためのOpenCVの関数。
  - TelloのIPアドレスとポート番号を指定して映像を受信。

---

### **並列処理でフレームを管理**
```python
self.capture_thread = Thread(target=self._capture_frames, daemon=True)
self.capture_thread.start()
```
- **`Thread`**:
  映像のズレを極力少なくするために、キューに最新のフレーム(画像)だけを格納する並列処理を行っています。

---

### **色検出の設定**
```python
h_min = 0
h_max = 7
s_min = 100
s_max = 255
v_min = 100
v_max = 255

bin_image = cv2.inRange(hsv_image, (h_min, s_min, v_min), (h_max, s_max, v_max))
```
- 赤色を検出するために、HSV値を指定。
- `cv2.inRange`を使って指定した範囲内の色を抽出（白色部分が検出部分）。

---

### **ラベリング処理**
```python
num_labels, label_image, stats, center = cv2.connectedComponentsWithStats(bin_image)
```
- **ラベリング**:
  - 色の領域ごとに番号を付けて特定。
  - 領域ごとの面積や重心を計算。

---

### **キーボード入力でドローン制御**
```python
if key == ord('t'):           # 離陸
    self.tello.takeoff()
elif key == ord('l'):           # 着陸
    self.tello.land()
elif key == ord('w'):           # 前進 30cm
    self.tello.move_forward(30)
...
```
- **`ord('文字')`**:
  - 特定のキーが押されたかを判定します。
- 各キーが押されると、Telloの対応する動作を実行します。
    - t: 離陸。
    - l: 着陸。
    - w: 前進
    - s: 後進
    - a: 左移動
    - d: 右移動
    - e: 時計回りに旋回
    - q: 反時計回りに旋回
    - r: 上昇
    - f: 下降
    - p: ステータスを表示
    - 1: 自動モードON
    - 0: 自動モードOFF
---

### **終了処理**
```python
def stop(self):
    self.tello.emergency()
    cv2.destroyAllWindows()
```
- **`emergency`**:
  - Telloの動作を完全に停止します。
- **`cv2.destroyAllWindows()`**:
  - OpenCVで開いていたウィンドウを閉じます。

---

# **動作の流れ**

1. **プログラム開始**:
   - ドローンと接続し、カメラ映像の受信を開始。

2. **色検出**:
   - カメラ映像の中から指定した色を検出。
   - 領域の面積や重心を計算。

3. **ドローンの制御**:
   - キーボード入力に応じてドローンを操作（例: 離陸、着陸、移動）。

4. **終了**:
   - ESCキーまたはウィンドウを閉じる操作でプログラムを終了。

---

# **プログラム実行コマンド**
次の手順でプログラムを実行します：

1. 必要なモジュールをインストール。
   ```bash
   pip install djitellopy opencv-python numpy
   ```
1. TelloドローンのWi-Fiに接続。
1. プログラムを保存（例: `color_tracking.py`）。
1. ターミナルまたはコマンドプロンプトで次を実行：
   ```bash
   python3 color_tracking.py
   ```
   Telloからの映像がPCに表示されるまで待つ

---

# **プログラム実行後の動作方法**

1. `t` キーを押して離陸させる
1. `1` キーを押して自動モードをONにする
1. 指定の色(デフォルトでは赤)をTelloの映像に映るようにする
1. 色を認識するとTelloが自動で指定の動作を実行する(デフォルトでは90度旋回し、30cm前進する)
1. `l` キーを押して着陸させる
1. `ESC` キーを押してプログラムを終了させる
