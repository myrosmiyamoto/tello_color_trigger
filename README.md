# はじめに
このプログラムはDJI Telloを使って映像の中で特定の色（デフォルトは赤色）を認識し、検出されたら指定の動作を行うプログラムとなっています。
DJI Telloを操作するために`djitellopy`のライブラリを使っています。
私の環境では`djitellopy`で映像を取得すると色合いがおかしくなる（おそらく`pyav`のバージョンの更新によるもの？）ので映像の処理は独自に実装しています。


# 必要なライブラリのインストール
ターミナル（コマンドプロンプト）で以下のコマンドを実行し、必要なライブラリをインストールします。
```bash
pip install djitellopy opencv-python numpy
```

- djitellopy：Telloドローンを制御するためのライブラリ
- opencv-python：カメラ映像を処理するためのライブラリ
- numpy：数値計算を行うためのライブラリ


# プログラム実行までの流れ
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

# プログラム実行後の流れ

1. `t` キーを押して離陸させる
1. `1` キーを押して自動モードをONにする
1. 指定の色(デフォルトでは赤)をTelloの映像に映るようにする
1. 色を認識するとTelloが自動で指定の動作を実行する(デフォルトでは90度旋回し、30cm前進する)
1. `l` キーを押して着陸させる
1. `ESC` キーを押してプログラムを終了させる


# 必要な知識
## HSV形式
### 色の表現方法について
私たちの目は、赤(R)・緑(G)・青(B)の3色の組み合わせで色を認識します。例えば：

- 赤 = (R:255, G:0, B:0)
- 緑 = (R:0, G:255, B:0)
- 青 = (R:0, G:0, B:255)

しかし、コンピュータで特定の色を見つけ出す場合、RGBは少し使いにくい方式です。そこでこのプログラムでは、HSV形式という別の色の表現方法を使っています。
### HSV形式とは？
HSVは色を3つの要素で表現します：
```python
# BGR画像をHSV形式に変換
hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
```

- H（色相：Hue）：色の種類を0〜180の数値で表します
  - 赤は0付近の値
  - 緑は60付近の値
  - 青は120付近の値

- S（彩度：Saturation）：色の鮮やかさを0〜255で表します
  - 0に近いほど白っぽく
  - 255に近いほど鮮やかに

- V（明度：Value）：色の明るさを0〜255で表します
  - 0は黒
  - 255は最も明るい

プログラムでは、特定の色をHSVで指定して検出しています。

## キュー (Queue)とは？
**キュー（Queue）**は、プログラミングで使われるデータを整理する方法の1つで、**「先に入れたものが先に出る」**というルールで動きます。このルールは英語で「**FIFO**（First In, First Out）」と呼ばれます。

プログラムでは映像の取得処理の並列実行時に最新の映像だけを取得するために使用しています。


# プログラムの各部分の詳細解説

## ヘッダー部分
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
```
- `#!/usr/bin/env python3`:
  - スクリプトをPython 3で実行することを指定します。
- `# -*- coding: utf-8 -*-`:
  - スクリプトの文字コードをUTF-8に設定します。

## ライブラリのインポート
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

## TelloControlクラス
このクラスはドローンを制御するすべての機能をまとめています。

### `__init__`（初期化メソッド）
```python
def __init__(self, ip, port):
    ...
```
- ドローンとの接続を確立
- カメラストリームの設定
- 各種フラグの初期化

```python
self.cap = cv2.VideoCapture(f'udp://{ip}:{port}')
```
- カメラ映像を取得するためのOpenCVの関数。
- TelloのIPアドレスとポート番号を指定して映像を受信。

### 並列処理でフレームを管理
```python
self.capture_thread = Thread(target=self._capture_frames, daemon=True)
self.capture_thread.start()
```
`Thread`と`Queue`を使い、映像のズレを極力少なくするために、キューに最新のフレーム(画像)だけを格納する並列処理を行っています。

## 色検出の設定
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

## ラベリング処理
```python
num_labels, label_image, stats, center = cv2.connectedComponentsWithStats(bin_image)
```
- **ラベリング**:
  - 色の領域ごとに番号を付けて特定
  - 領域ごとの面積や重心を計算

## 黒色の領域の削除
```python
# 最大のラベルは画面全体を覆う黒なので不要．データを削除
num_labels = num_labels - 1
stats = np.delete(stats, 0, 0)
center = np.delete(center, 0, 0)
```

黒で塗りつぶされた背景色全体も1つのラベルとして認識される。ほとんどの映像では1個目のラベルに背景色になるため1個目のラベルを削除する処理をしています。


## 面積が最大のラベルだけを抽出
```python
if num_labels >= 1:
      # 面積最大のインデックスを取得
      max_index = np.argmax(stats[:,4])

      # 面積が最大のx,y,w,h,面積s,重心位置mx,myだけを取得
      x = stats[max_index][0]
      y = stats[max_index][1]
      w = stats[max_index][2]
      h = stats[max_index][3]
      s = stats[max_index][4]
      mx = int(center[max_index][0])
      my = int(center[max_index][1])
```
面積が最大のラベルの値を使って自動で指定の動作をするかどうかを判定します。

## 自動モード
```python
if s > 20000 and self.is_automode and not self.is_tello_control:
  ...
```
赤色物体の面積が20000ピクセル以上で、自動モードがONの場合に自動で指定の動作を開始します。

## キーボード入力でドローン制御
```python
def _tello_control(self, control_flag):
    if control_flag == 'w':
        self.tello.move_forward(30)  # 前進 30cm
    ...
```

- 各キーが押されると、Telloの対応する動作を実行します。
  - t: 離陸
  - l: 着陸
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

## 終了処理
```python
def stop(self):
    self.tello.emergency()
    cv2.destroyAllWindows()
```
- **`emergency`**:
  - Telloの動作を完全に停止します。
- **`cv2.destroyAllWindows()`**:
  - OpenCVで開いていたウィンドウを閉じます。

# 参考
このプログラムは下記のサイトを参考にしております。
- [DJI公式SDK「Tello-Python」を試そう](https://qiita.com/hsgucci/items/3327cc29ddf10a321f3c)
- [色検出プログラム](https://qiita.com/hsgucci/items/e9a65d4fa3d279e4219e)
