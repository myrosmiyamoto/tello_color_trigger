#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from djitellopy import Tello, TelloException    # DJITelloPyのTelloクラスをインポート
import sys                                      # sys.exitを使うため
import time                                     # time.sleepを使うため
import cv2                                      # OpenCVを使うため
from threading import Thread                    # 並列処理をするため
from queue import Queue                         # 最新の映像にするため
import numpy as np                              # ラベリングにNumPyが必要なため



# Telloを制御するクラス
class TelloControl:
    # コンストラクタ
    def __init__(self, ip, port):
        # 初期化部
        Tello.RETRY_COUNT = 1          # retry_countは応答が来ないときのリトライ回数
        Tello.RESPONSE_TIMEOUT = 0.01  # 応答が来ないときのタイムアウト時間
        # Telloクラスを使って，tellというインスタンス(実体)を作る
        self.tello = Tello()

        try:
            # Telloへ接続
            self.tello.connect()

            # 画像転送を有効にする
            self.tello.streamoff()   # 誤動作防止の為、最初にOFFする
            self.tello.streamon()    # 画像転送をONに
        except KeyboardInterrupt:
            print('\n[Finish] Press Ctrl+C to exit')
            sys.exit()
        except TelloException:
            print('\n[Finish] Connection timeout')
            sys.exit()

        # フラグ関係
        self.is_running = True         # Telloが動作中か
        self.is_tello_control = False  # Telloを制御しているかどうか
        self.is_automode = False       # 自動制御を行うかどうか

        # カメラストリームを取得
        self.cap = cv2.VideoCapture(f'udp://{ip}:{port}')
        # 画像の幅と高さを設定
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) / 2)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) / 2)

        self.frame_name = f'Tello {ip}'
        self.frame_queue = Queue(maxsize=1)  # 最新フレームを保持するキュー

        # フレームをキャプチャするスレッドを開始
        self.capture_thread = Thread(target=self._capture_frames, daemon=True)
        self.capture_thread.start()

        # Telloが10秒で自動的に制御停止するのを防ぐ処理のための変数
        self.current_time = time.time()    # 現在時刻の保存変数
        self.pre_time = self.current_time  # 前回の'command'送信時を記録するための時刻変数


    # Telloからの映像を最新の画像だけをキューに保持するための関数
    def _capture_frames(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if ret:
                # 最新フレームのみを保持
                if not self.frame_queue.empty():
                    # キューからフレームを取り出す
                    self.frame_queue.get_nowait()
                self.frame_queue.put(frame)


    # Tello制御のメインの関数
    def run(self):
        if self.is_running:
            if not self.frame_queue.empty():  # キューの中が空でなければ処理を実行する
                frame = self.frame_queue.get()  # キューの値を取得
                # フレームのリサイズ
                resized_frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)

                # Telloからの映像を表示
                cv2.imshow(self.frame_name, resized_frame)

                # ここから画像処理
                bgr_image = resized_frame
                hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)  # BGR画像 -> HSV画像

                # 赤色のHSVの値域
                # ここの値を変更することで他の色にも対応できる
                h_min = 0    # 色相の最小値
                h_max = 7    # 色相の最大値
                s_min = 100  # 彩度の最小値
                s_max = 255  # 彩度の最大値
                v_min = 100  # 明度の最小値
                v_max = 255  # 明度の最大値

                # inRange関数で範囲指定2値化
                bin_image = cv2.inRange(hsv_image, (h_min, s_min, v_min), (h_max, s_max, v_max)) # HSV画像なのでタプルもHSV並び

                # bitwise_andで元画像にマスクをかける -> マスクされた部分の色だけ残る
                result_image = cv2.bitwise_and(hsv_image, hsv_image, mask=bin_image)   # HSV画像 AND HSV画像 なので，自分自身とのANDは何も変化しない->マスクだけ効かせる

                # 面積・重心計算付きのラベリング処理を行う
                num_labels, label_image, stats, center = cv2.connectedComponentsWithStats(bin_image)

                # 最大のラベルは画面全体を覆う黒なので不要．データを削除
                num_labels = num_labels - 1
                stats = np.delete(stats, 0, 0)
                center = np.delete(center, 0, 0)

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

                    # ラベルを囲うバウンディングボックスを描画
                    cv2.rectangle(result_image, (x, y), (x+w, y+h), (255, 0, 255))

                    # 重心位置の座標と面積を表示
                    cv2.putText(result_image, "%d,%d"%(mx,my), (x-15, y+h+15), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 0))
                    cv2.putText(result_image, "%d"%(s), (x, y+h+30), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 0))

                    # 面積が2000以上なら自動モード作動
                    if  s > 20000 and self.is_automode and not self.is_tello_control:
                        Thread(target=self._tello_control, args=('color_trigger', )).start()

                cv2.imshow('Result Image', result_image)

                key = cv2.waitKey(1) & 0xFF
                # ESCキーが押されたら、また、ウィンドウが終了したらストップ
                if not self.is_tello_control:
                    if key == 27 or cv2.getWindowProperty(self.frame_name, cv2.WND_PROP_AUTOSIZE) == -1:
                        print('[Finish] Press ESC key or close window to exit')
                        self.stop()
                    elif key == ord('t'):  # 離陸
                        self.tello.takeoff()
                    elif key == ord('l'):  # 着陸
                        self.tello.land()
                    elif key == ord('w'):  # 前進 30cm
                        Thread(target=self._tello_control, args=('w', )).start()
                    elif key == ord('s'):  # 後進 30cm
                        Thread(target=self._tello_control, args=('s', )).start()
                    elif key == ord('a'):  # 左移動 30cm
                        Thread(target=self._tello_control, args=('a', )).start()
                    elif key == ord('d'):  # 右移動30cm
                        Thread(target=self._tello_control, args=('d', )).start()
                    elif key == ord('e'):  # 旋回-時計回り 30度
                        Thread(target=self._tello_control, args=('e', )).start()
                    elif key == ord('q'):  # 旋回-反時計回り 30度
                        Thread(target=self._tello_control, args=('q', )).start()
                    elif key == ord('r'):  # 上昇 30cm
                        Thread(target=self._tello_control, args=('r', )).start()
                    elif key == ord('f'):  # 下降 30cm
                        Thread(target=self._tello_control, args=('f', )).start()
                    elif key == ord('p'):  # ステータスをprintする
                        print(self.tello.get_current_state())
                    elif key == ord('1'):  # 自動モードON
                        self.is_automode = True
                        print('オートモードON')
                    elif key == ord('0'):  # 自動モードOFF
                        self.tello.send_rc_control(0, 0, 0, 0)
                        self.is_automode = False

                # 10秒おきに'command'を送って、死活チェックを通す
                self.current_time = time.time()                          # 現在時刻を取得
                if not self.is_tello_control and self.current_time - self.pre_time > 10.0 :                 # 前回時刻から10秒以上経過しているか？
                    self.tello.send_command_without_return('command')    # 'command'送信
                    self.pre_time = self.current_time                         # 前回時刻を更新


    # 終了処理の関数
    def stop(self):
        self.tello.emergency()  # Telloの動作を完全に停止
        print(f'[Battery] {self.tello.get_battery()}%')  # バッテリー残量を表示
        self.is_running = False  # ストリームを停止
        self.capture_thread.join()  # スレッドを終了
        cv2.destroyAllWindows()  # ウィンドウを閉じる
        self.tello.streamoff()
        if self.cap.isOpened():
            self.cap.release()  # カメラを開放
        self.tello.end()


    # Telloが動作しているか確認するための関数
    def is_run(self):
        return self.is_running


    # Telloを動かすための関数
    def _tello_control(self, control_flag):
        self.is_tello_control = True
        if control_flag == 'w':  # 前進 30cm
            self.tello.move_forward(30)
            time.sleep(1)
        elif control_flag == 's':  # 後進 30cm
            self.tello.move_back(30)
            time.sleep(1)
        elif control_flag == 'a':  # 左移動 30cm
            self.tello.move_left(30)
            time.sleep(1)
        elif control_flag == 'd':  # 右移動30cm
            self.tello.move_right(30)
            time.sleep(1)
        elif control_flag == 'e':  # 時計回りに旋回 30度
            self.tello.rotate_clockwise(30)
            time.sleep(1)
        elif control_flag == 'q':  # 反時計回りに旋回 30度
            self.tello.rotate_counter_clockwise(30)
            time.sleep(1)
        elif control_flag == 'r':  # 上昇 30cm
            self.tello.move_up(30)
            time.sleep(1)
        elif control_flag == 'f':  # 下降 30cm
            self.tello.move_down(30)
            time.sleep(1)
        elif control_flag == 'color_trigger':
            self.tello.rotate_clockwise(90)
            time.sleep(3)
            self.tello.move_forward(50)
            time.sleep(3)
        self.is_tello_control = False
        self.current_time = time.time()  # 現在時刻を取得
        self.pre_time = self.current_time  # 前回時刻を更新



# メイン関数
def main():
    ip = '192.168.10.1'
    port = '11111'

    tello = TelloControl(ip, port)
    try:
        # 永久ループで繰り返す
        while tello.is_run():
            tello.run()
    except(KeyboardInterrupt, SystemExit):    # Ctrl+cが押されたらループ脱出
        print('[Finish] Press Ctrl+C to exit')
        tello.stop()
        sys.exit()


# "python3 color_tracking.py"として実行された時だけ動く様にするおまじない処理
if __name__ == "__main__":      # importされると__name_に"__main__"は入らないので，pyファイルが実行されたのかimportされたのかを判断できる．
    main()    # メイン関数を実行
