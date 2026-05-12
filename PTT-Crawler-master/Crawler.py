# -*- coding: UTF-8 -*-

import json
import requests
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from bs4.element import NavigableString

def main():
    board = "Gossiping"
    crawler = PttCrawler()
    crawler.crawl_by_date(board=board, target_date="2025-01-01")

class PttCrawler:
    root = "https://www.ptt.cc/bbs/"
    main = "https://www.ptt.cc"
    gossip_data = {"from": "bbs/Gossiping/index.html", "yes": "yes"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def __init__(self):
        self.session = requests.session()
        self.session.headers.update(self.headers)
        requests.packages.urllib3.disable_warnings()
        self._safe_request("POST", "https://www.ptt.cc/ask/over18", data=self.gossip_data)

    def _safe_request(self, method, url, **kwargs):
        max_retries = 5
        backoff = 2
        for i in range(max_retries):
            try:
                if method == "GET":
                    return self.session.get(url, verify=False, **kwargs)
                elif method == "POST":
                    return self.session.post(url, verify=False, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if i == max_retries - 1:
                    raise e
                wait = backoff ** (i + 1)
                print(f"Connection error, retrying in {wait}s... ({i+1}/{max_retries})")
                time.sleep(wait)

    def articles(self, page):
        res = self._safe_request("GET", page)
        soup = BeautifulSoup(res.text, "lxml")
        for article in soup.select(".r-ent"):
            try:
                yield self.main + article.select(".title")[0].select("a")[0].get("href")
            except:
                pass

    def parse_article(self, url, mode="all"):
        if mode == "all": 
            mode_tag = "all"
        elif mode == "up": 
            mode_tag = "推"
        elif mode == "down": 
            mode_tag = "噓"
        elif mode == "normal": 
            mode_tag = "→"
        else: 
            raise ValueError("mode變數錯誤", mode)

        try:
            raw = self._safe_request("GET", url)
            soup = BeautifulSoup(raw.text, "lxml")
            article = {}
            meta = soup.select(".article-meta-value")
            if len(meta) < 4:
                return None
            
            article["Author"] = meta[0].text.strip().split(" ")[0]
            article["Title"] = meta[2].text.strip()
            article["Date"] = meta[3].text.strip().strip(" []")

            content_div = soup.select_one("#main-content")
            if content_div:
                article["Content"] = content_div.get_text(separator="\n", strip=True)
            else:
                article["Content"] = ""

            upvote, downvote, novote = 0, 0, 0
            response_list = []
            for response_struct in soup.select(".push"):
                if "warning-box" not in response_struct["class"]:
                    try:
                        content = response_struct.select_one(".push-content").text.strip()[1:]
                        vote = response_struct.select_one(".push-tag").text.strip()[0]
                        user = response_struct.select_one(".push-userid").text.strip()
                        response_dic = {"Content": content, "Vote": vote, "User": user}

                        if mode_tag == "all" or vote == mode_tag:
                            response_list.append(response_dic)
                            if vote == "推": upvote += 1
                            elif vote == "噓": downvote += 1
                            else: novote += 1
                    except:
                        continue

            article["Responses"] = response_list
            article["UpVote"] = upvote
            article["DownVote"] = downvote
            article["NoVote"] = novote
            return article
        except Exception as e:
            print(f"Error parsing {url}: {e}")
            return None

    def output(self, filename, data):
        try:
            with open(f"{filename}.json", "w", encoding="utf-8") as op:
                json.dump(data, op, indent=4, ensure_ascii=False)
                print(f"成功輸出 {filename}.json")
        except Exception as err:
            print(f"輸出失敗 {filename}.json: {err}")

    def crawl_by_date(self, board="Gossiping", target_date="2025-01-01", sleep_time=1.0, max_workers=4):
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        page_idx = 1
        output_dir = f"data_{board}_2025"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        while True:
            page_url = f"{self.root}{board}/index{page_idx}.html" if page_idx > 1 else f"{self.root}{board}/index.html"
            print(f"正在平行爬取第 {page_idx} 頁: {page_url}")
            try:
                urls = list(self.articles(page_url))
            except Exception as e:
                print(f"頁面 {page_idx} 索引爬取失敗: {e}")
                time.sleep(5)
                continue

            if not urls:
                print("沒有發現文章，停止爬取。")
                break
            
            page_data = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_url = {executor.submit(self.parse_article, url): url for url in urls}
                for future in as_completed(future_to_url):
                    art = future.result()
                    if art:
                        page_data.append(art)
            
            if page_data:
                dates = []
                for a in page_data:
                    try:
                        # PTT Date format: "Sat Sep 24 14:44:19 2005"
                        dates.append(datetime.strptime(a["Date"], "%a %b %d %H:%M:%S %Y"))
                    except: pass
                
                if dates and min(dates) < target_dt:
                    print(f"發現日期已早於 {target_date}，完成本頁後停止爬取。")
                    self.output(f"{output_dir}/{board}_{page_idx}", page_data)
                    return

            self.output(f"{output_dir}/{board}_{page_idx}", page_data)
            page_idx += 1
            time.sleep(sleep_time)

if __name__ == "__main__":
    main()
