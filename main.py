import requests, time, json, os
from bs4 import BeautifulSoup
from ebooklib import epub
from rich.progress import Progress
from PIL import Image

def validImage(file_name):
    try:
        with Image.open(file_name) as img:
            img.verify()
            return True
    except (IOError, SyntaxError):
        return False

def getChapterURLs(url:str) -> dict:
    r = []
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    bookID = int(str(soup.find('div', class_="layout").find('script').text).split('bookId = ', 1)[1].split(";")[0])
    response = requests.get(f'https://novelbuddy.com/api/manga/{bookID}/chapters?source=detail')
    soup = BeautifulSoup(response.content, 'html.parser')
    with Progress() as p:
        t = p.add_task("Processing chapter URLs...", total=len(soup.find_all('li')))
        for i in soup.find_all('li'):
            r.append(i.find('a').attrs)
            p.update(t, advance=1)
    r.reverse()
    return r

def getChapterText(chs:list) -> dict:
    collec = {}
    with Progress() as p:
        t = p.add_task("Processing chapter text...", total=len(chs))
        for i in chs:
            response = requests.get(f'https://novelbuddy.com{dict(i)['href']}')
            soup = BeautifulSoup(response.content, 'html.parser')
            container = soup.find('div', class_='content-inner')
            collec[dict(i)['title']] = container.prettify()
            p.update(t, advance=1)
    return collec

def getNovelDetails(url:str, getcover=True) -> dict:
    r = {}
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    r['title'] = soup.find('div', class_='name box').find('h1').text
    r['author'] = soup.find('div', class_='meta box mt-1 p-10').find('p').find('a').attrs['title']
    if getcover:
        coverURl = "https:" + soup.find('div', class_="img-cover").find('img').attrs['data-src']
        coverImage = requests.get(coverURl).content
        ext = coverURl.split('.', 3)[3]
        with open(f'./cache/{r['title']}.{ext}', 'wb') as f:
            f.write(coverImage)
            f.close()
        r['cover'] = f'./cache/{r['title']}.{ext}'
    else:
        r['cover'] = None
    return r

def writeToEPUB(chs:dict, details:dict):
    book = epub.EpubBook()
    book.set_title(details['title'])
    book.set_language("en")
    book.add_author(details['author'])
    with open(details['cover'], "rb") as f:
        img = f.read()
        f.close()
        if validImage(details['cover']):
            book.set_cover(f'image.{details['cover'].split('.')[1]}', img)
    book.spine = ["nav"]
    for i in chs.items():
        c = epub.EpubHtml(title=i[0], file_name=f"{i[0]}.xhtml", lang="en")
        c.set_content(i[1])
        book.add_item(c)
        book.toc.append(epub.Link(href=f"{i[0]}.xhtml", title=i[0]))
        book.spine.append(c)

    #book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    with open('./css/base.css') as f:
        style = f.read() #'body { font-family: Times, Times New Roman, serif; }'
    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(nav_css)
    epub.write_epub(f"./results/{details['title']}.epub", book)

def main():
    if not os.path.exists('./results'):
        os.makedirs('./results')
    if not os.path.exists('./cache'):
        os.makedirs('./cache')
    with open("config.json", 'r') as f:
        d = json.load(f)
        url = d['url']
        getcover = d['getCover']
    chapterURLS = getChapterURLs(url)
    print("Successfully got chapter urls!")
    sTime = time.time()
    novelDetails = getNovelDetails(url, getcover)
    print(f"Successfully got novel details in {round(time.time() - sTime, 1)}s")
    chapterText = getChapterText(chapterURLS)
    print(f"Successfully processed chapter text!")
    sTime = time.time()
    writeToEPUB(chapterText, novelDetails)
    print(f"Successfully wrote novel to epub in {round(time.time() - sTime, 1)}s!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("Program encountered fatal error:", e)