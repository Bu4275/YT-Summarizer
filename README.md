## Installation


- 安裝 ffmpeg，並將 ffmpeg 執行檔路徑加入環境變數
https://www.ffmpeg.org/download.html#build-mac

- 安裝 Python 相依套件
```
pip install -r requirement.txt
```

- 設定 .env 檔案，修改 `OPENAI_API_KEY`


- 安裝 cuda，建議查看 pytorch 支援的 cuda 版本
https://pytorch.org/get-started/locally/


## Usage

```
python app.py
```

- Go to http://127.0.0.1:5000