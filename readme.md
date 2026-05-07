# Nebula
在廣大的中文Blog圈，用Blogrooll 探索所有的Blog！
一個程式可以讓你探索所有用Blogroll串起的Blog

(話說Nebula中文是星雲，我想要代表在廣大宇宙尋找?)
# 程式說明
自動探索網站的 blogroll / links / friends 頁面，建立網站之間的連結圖，並可視覺化成互動式網路圖。

- BFS 遞迴探索 blog network
- 互動式視覺化
- 產生 graph JSON

已經有附上結果了(2026_05_07的結果，可以試試看)

## 安裝&使用說明
```
pip install aiohttp beautifulsoup4 pyvis
```
```
python blogroll_crawler.py
```
預設起點為https://blog.giveanornot.com/blogroll/

若要指定起點
```
python blogroll_crawler.py \
  --seed https://example.com/blogroll
```
輸出結果
```
python visualize_graph.py
```
用瀏覽器開啟blogroll_graph.html

# License
GPL V2
