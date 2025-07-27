import requests, time, pypub, json
from bs4 import BeautifulSoup

def getChapterURLs(url:str) -> dict:
    r = []
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    bookID = int(str(soup.find('div', class_="layout").find('script').text).split('bookId = ', 1)[1].split(";")[0])
    response = requests.get(f'https://novelbuddy.com/api/manga/{bookID}/chapters?source=detail')
    soup = BeautifulSoup(response.content, 'html.parser')
    for i in soup.find_all('li'):
        r.append(i.find('a').attrs)
    return r

def getChapterText(chs:list) -> dict:
    collec = {}
    for i in chs:
        response = requests.get(f'https://novelbuddy.com/{dict(i)['href']}')
        soup = BeautifulSoup(response.content, 'html.parser')
        container = soup.find('div', class_='content-inner').find('div')
        text = ""
        for t in container.find_all('p'):
            text += f"{t.text}\n"
        collec[dict(i)['title']] = text
    return collec

def getNovelDetails(url:str) -> dict:
    r = {}
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    r['title'] = soup.find('div', class_='name box').find('h1').text
    r['author'] = soup.find('div', class_='meta box mt-1 p-10').find('p').find('a').attrs['title']
    return r

def writeToEPUB(chs:dict, details:dict):
    book = pypub.Epub(details['title'], language='en', creator=details['author'])
    for i in chs.items():
        c = pypub.create_chapter_from_text(i[1], title=i[0])
        book.add_chapter(c)
    book.create(f"./results/{details['title']}.epub")

def main():
    with open("config.json", 'r') as f:
        d = json.load(f)
        url = d['url']
    sTime = time.time()
    chapterURLS = getChapterURLs(url)
    novelDetails = getNovelDetails(url)
    print(f"Successfully got chapter URLs and novel details in {time.time() - sTime}s")
    sTime = time.time()
    chapterText = getChapterText(chapterURLS)
    print(f"Successfully got chapter text in {time.time() - sTime}s!")
    sTime = time.time()
    writeToEPUB(chapterText, novelDetails)
    print(f"Successfully wrote novel to epub in {time.time() - sTime}s!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("Program encountered error:", e)