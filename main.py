import requests, time, os, threading, gc
from argparse import ArgumentParser
from ebooklib import epub
from bs4 import BeautifulSoup
from rich.progress import Progress
from PIL import Image

def validImage(file_name):
    try:
        with Image.open(file_name) as img:
            img.verify()
            return True
    except (IOError, SyntaxError):
        return False

def cleanFileName(filename:str) -> str:
    filename = filename.replace('<','')
    filename = filename.replace('>', '')
    filename = filename.replace(':', '')
    filename = filename.replace('/', '')
    filename = filename.replace('\\', '')
    filename = filename.replace('|', '')
    filename = filename.replace('?', '')
    filename = filename.replace('*', '')
    return filename

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

def textWorker(chs:list, comp:dict, num:int):
    collec = {}
    with Progress() as p:
        t = p.add_task(f"Processing chapter text for chunk {num}...", total=len(chs))
        for i in chs:
            response = requests.get(f'https://novelbuddy.com{dict(i)['href']}')
            soup = BeautifulSoup(response.content, 'html.parser')
            container = soup.find('div', class_='content-inner')
            collec[dict(i)['title']] = container.prettify()
            p.update(t, advance=1)
    comp[num] = collec


def splitIntoChunks(data, threads) -> list:
    chunk_size = (len(data) + threads - 1) // threads
    return [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]


def getChapterText(chs:list, n:str, sn:str, wrkrs:int = 5) -> dict:
    collec = {}
    sn = int(sn)
    if not str(n).isnumeric() and n == "all":
        n = len(chs)
    else:
        n = int(n)
    chs = chs[sn:n]
    chunkSize = splitIntoChunks(chs, wrkrs)
    for i in range(wrkrs):
        threading.Thread(target=textWorker, daemon=True, args=(chunkSize[i], collec, i)).start()
    while len(collec.keys()) != wrkrs:
        pass
    # print(collec.keys()); os._exit(0)
    fcollec = {}
    for i in range(wrkrs):
        for c in collec[i].items():
            fcollec[c[0]] = c[1]
    return fcollec

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
        path = f'./cache/{cleanFileName(r['title'])}.{ext}'
        with open(path, 'wb') as f:
            f.write(coverImage)
            f.close()
        r['cover'] = path
    else:
        r['cover'] = None
    return r

def writeToEPUB(chs:dict, details:dict):
    gc.collect()
    book = epub.EpubBook()
    book.set_title(details['title'])
    book.set_language("en")
    book.add_author(details['author'])
    if details['cover'] != None:
        with open(details['cover'], "rb") as f:
            img = f.read()
            f.close()
            if validImage(details['cover']):
                book.set_cover(f'image.{details['cover'].split('.')[1]}', img)
    else:
        print("Skipped adding cover!")
    book.spine = ["nav"]
    for i in chs.items():
        c = epub.EpubHtml(title=i[0], file_name=f"{i[0]}.xhtml", lang="en")
        c.set_content(i[1])
        #c.properties.append('rendition:layout-pre-paginated rendition:orientation-landscape rendition:spread-none')
        book.add_item(c)
        book.toc.append(epub.Link(href=f"{i[0]}.xhtml", title=i[0]))
        book.spine.append(c)
    book.add_item(epub.EpubNav())
    with open('./css/base.css') as f:
        style = f.read()
    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(nav_css)
    epub.write_epub(f"./results/{cleanFileName(details['title'])}.epub", book, {})

def main():
    if not os.path.exists('./cache'):
        os.makedirs('./cache')
    if not os.path.exists('./results'):
        os.makedirs('./results')
    parser = ArgumentParser()
    parser.add_argument('-u', '--url', action="store")
    parser.add_argument('-c', '--chapters', action="store", default="all")
    parser.add_argument('-gc', '--getcover', action="store_true")
    parser.add_argument('-sc', '--startchapter', action="store", default=0)
    parser.add_argument('-w', '--workers', action="store", default=5)
    args = parser.parse_args()
    chapterURLS = getChapterURLs(args.url)
    print("Successfully got chapter urls!")
    sTime = time.time()
    novelDetails = getNovelDetails(args.url, args.getcover)
    print(f"Successfully got novel details in {round(time.time() - sTime, 1)}s")
    chapterText = getChapterText(chapterURLS, args.chapters, args.startchapter, int(args.workers))
    print(f"Successfully processed chapter text!")
    sTime = time.time()
    writeToEPUB(chapterText, novelDetails)
    print(f"Successfully wrote novel to epub in {round(time.time() - sTime, 1)}s!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("Program encountered fatal error:", e)
