import json
import re
import requests
import time
from requests import RequestException
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pymongo
from config import *

start = time.clock()     # 记录程序开始时间
total_page = 0           # 此变量保存索引页的页面数量
count = 0                # 此变量保存存储到数据库的记录数量
browser = webdriver.Chrome()
wait = WebDriverWait(browser, 10)
client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Host': 'www.lagou.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/49.0.2623.221 Safari/537.36 SE 2.X MetaSr 1.0',
    'Cookie': '请登录您的拉勾网账号后，在此填写自己的cookie信息'
}


# 请求初始URL，结果返回页面源码（此URL为最初的索引页）
def get_first_page(url):
    try:
        browser.get(url)
        total_index_page = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#s_position_list > div.item_con_pager > div > span:nth-child(5)')))
        # 声明全局变量，此变量保存索引页的页面数量
        global total_page
        total_page = total_index_page.text
        return browser.page_source
    except TimeoutException:
        print('请求超时，重新连接中...')
        return get_first_page()


# 正则解析索引页，获取并返回所有详情页的链接
def parse_index_page(index_html):
    pattern = re.compile('<a class="position_link" href="(.*?)" target="_blank"', re.S)
    contents = re.findall(pattern, index_html)
    return contents


# 请求详情页，结果返回页面源码
def get_detail_page(url):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('Σ(っ °Д °;)っ 请求详情页出错\n')
        return None


# 使用BeautifulSoup解析详情页，信息存入字典info中，接着调用存储到数据库/文本文档的函数
def parse_detail_page(detail_html):
    soup = BeautifulSoup(detail_html, 'lxml')
    try:
        job_advantage = soup.select('#job_detail > dd.job-advantage')[0].get_text()
        job_location = soup.select('#job_detail > dd.job-address.clearfix > div.work_addr')[0].get_text()
        job_description = soup.select('#job_detail > dd.job_bt > div')[0].get_text()
        job_request = soup.find('dd', {'class': 'job_request'}).p
        info = {
            '职位名': soup.select('body > div.position-head > div > div.position-content-l > div > span')[0].get_text(),
            '薪酬': job_request.contents[1].string,
            '公司': soup.select('body > div.position-head > div > div.position-content-l > div > div.company')[0].get_text(),
            '公司主页': soup.find('i', {'class': 'icon-glyph-home'}).find_next_sibling('a').string,
            '工作地点': "".join(job_location.split())[:-4],
            '工作经验': job_request.contents[5].string[:-1],
            '学历要求': job_request.contents[7].string[:-1],
            '工作性质': job_request.contents[9].string[:-1],
            '职位诱惑': job_advantage.replace("\n", ""),
            '职位描述': "".join(job_description).split()
        }
        #save_to_file(info)
        save_to_mongo(info)
        # 声明全局变量，此变量保存存储到数据库的记录数量
        global count
        count += 1
    except Exception:
        print('Σ(っ °Д °;)っ 解析详情页出错\n')


# 请求下一页索引页
def get_next_index():
    try:
        # 拖动浏览器到页面最底端
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        # 等待下一页框可点击
        next_page = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '#s_position_list > div.item_con_pager > div > span.pager_next')))
        next_page.click()
    except TimeoutException:
        print('请求下一页索引页超时，重新请求中...')
        get_next_index()


# 保存到MONGOdb数据库
def save_to_mongo(result):
    try:
        if db[MONGO_TABLE].insert(result):
            print('存储到MONGODB成功\n')
    except Exception:
        print('存储到MONGODB失败\n', result['公司'])


# 保存到文本文档
def save_to_file(item):
    try:
        with open('job.txt', 'a', encoding='utf-8') as f:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            f.close()
    except Exception:
        print('存储失败', item)


def main():
    try:
        url = 'https://www.lagou.com/jobs/list_' + KEYWORD + '?&px=default&city=全国#filterBox'
        index_html = get_first_page(url)
        print('招聘信息总页数：', total_page)
        for i in range(1, int(total_page)+1):
            print('存储第' + str(i) + '页招聘信息中')
            links = parse_index_page(index_html)
            for link in links:
                detail_html = get_detail_page(link)
                parse_detail_page(detail_html)
            get_next_index()
            time.sleep(2)
            index_html = browser.page_source
        print('爬虫结束！爬取信息 %d 页，共计 %d 条数据' % (int(total_page), count))
        spent_time = (time.clock() - start)
        print("程序用时: %.2f" % spent_time)
    except Exception:
        print('出现异常')
    finally:
        browser.close()


if __name__ == '__main__':
    main()