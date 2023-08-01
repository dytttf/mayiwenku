# coding:utf8
import re
import os
import time
import argparse
import traceback

import requests
from reportlab.platypus import SimpleDocTemplate, Image, PageBreak
from reportlab.lib.pagesizes import A4, landscape
from PIL import Image as pilImage

# 当前路径
cur_path = os.path.dirname(os.path.abspath(__file__))


class MaYiWenKu(object):
    def __init__(self, data_dir=None):
        #
        self.data_dir = data_dir or cur_path
        #
        self.base_headers = {
            "Accept": "*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.mayiwenku.com",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36",
        }

    def log(self, *messages):
        if len(messages) == 1 and isinstance(messages[0], Exception):
            traceback.print_exc()
        else:
            print(*messages)
        return

    def get_image_size(self, image_path):
        img = pilImage.open(image_path)
        size = img.size
        img.close()
        return size

    def cut_image(self, image_path, size):
        img = pilImage.open(image_path)
        #
        w_radio = 0.8
        h_radio = 0.9
        w, h = img.size
        box = (
            int(w * (1 - w_radio) / 2 + 1),
            int(h * (1 - h_radio) / 2 + 1),
            w - int(w * (1 - w_radio) / 2 + 1),
            h - int(h * (1 - h_radio) / 2 + 1),
        )
        region = img.crop(box)

        img1 = pilImage.new(img.mode, size=(box[2] - box[0], box[3] - box[1]))
        img1.paste(region)
        img1 = img1.resize(size, pilImage.LANCZOS)
        new_image_path = re.sub("(\d+).gif", "\\1_handle.png", image_path)
        img1.save(new_image_path, quality=100)

        img1.close()
        img.close()
        return new_image_path

    def images2pdf(self, image_dir):
        # A4 纸的宽高
        a4_height, a4_width = landscape(A4)

        # 获取图片列表并排序
        image_list = []
        for image_name in os.listdir(image_dir):
            if not image_name.endswith(".gif"):
                continue
            if "handle" in image_name:
                continue
            image_list.append(image_name)
        image_list.sort(key=lambda x: int(x.split(".")[0]))

        bookPagesData = []

        pdf_page_kwargs = {
            "leftMargin": 0,
            "rightMargin": 0,
            "topMargin": 0,
            "bottomMargin": 0,
        }
        save_book_name = "{}.pdf".format(image_dir)

        for image_name in image_list:
            image_real_path = os.path.join(image_dir, image_name)
            # 处理图片
            image_real_path = self.cut_image(
                image_real_path, (int(a4_width * 0.95), int(a4_height * 0.95))
            )
            image_width, image_height = self.get_image_size(image_real_path)
            data = Image(image_real_path, image_width, image_height)

            bookPagesData.append(data)
            bookPagesData.append(PageBreak())

        try:
            bookDoc = SimpleDocTemplate(save_book_name, pagesize=A4, **pdf_page_kwargs)
            bookDoc.build(bookPagesData)
            self.log("pdf 转换完成: {}".format(save_book_name))
        except Exception as err:
            self.log("pdf 转换失败: {}".format(save_book_name))
            self.log(err)
        return

    def download_image(self, image_url, document_url):
        headers = self.base_headers.copy()
        headers.update(
            {
                "Referer": document_url,
            }
        )
        resp = requests.get(image_url, headers=headers)
        return resp.content

    def get_document_info(self, document_url):
        """获取文档基本信息"""
        headers = self.base_headers
        resp = requests.get(document_url, headers=headers)
        #
        # image_base = re.search("input\s*type=\"hidden\"\s*id=\"dp\"\s*value=\"([^\"]+)", resp.text).group(1)
        image_base = re.search(
            'input\s*type="hidden"\s*id="dp"\s*value="([^"]+)"', resp.text
        ).group(1)
        max_page = re.search("var fCount = (\d+);", resp.text).group(1)
        title = re.search("title>(.*?)_蚂蚁文库", resp.text).group(1)
        info = {
            "image_base": image_base,
            "max_page": max_page,
            "title": title,
        }
        return info

    def get_document(self, url, max_page=None):
        # 获取文档基本信息
        document_info = self.get_document_info(url)
        title = document_info["title"]
        image_base_url = document_info["image_base"]
        max_page = max_page or int(document_info["max_page"])
        #
        self.log("""文档名称: {}\n总页码: {}\n开始下载...""".format(title, max_page))
        #
        image_dir = os.path.join(self.data_dir, "蚂蚁文库_%s" % title)
        os.makedirs(image_dir, exist_ok=True)

        for page_index in range(1, max_page + 1):
            image_path = os.path.join(image_dir, "{}.gif".format(page_index))
            if not os.path.exists(image_path):
                image_part_url = "{}{}.gif".format(image_base_url, page_index)
                image_content = self.download_image(image_part_url, url)
                with open(image_path, "wb") as f:
                    f.write(image_content)
                self.log("\t第{}页下载成功: {}".format(page_index, image_part_url))
                time.sleep(1)
            else:
                self.log("\t第{}页已存在".format(page_index))
        return image_dir


def get_cmd_args():
    parser = argparse.ArgumentParser(
        prog="Program Name (default: sys.argv[0])", description="蚂蚁文库下载器", add_help=True
    )
    parser.add_argument("--url", action="store", help="待下载文档url")
    parser.add_argument("--max_page", action="store", help="待下载文档最大页码 默认全部下载")
    parser.add_argument("--data_dir", action="store", help="下载文件保存路径")
    return parser.parse_args()


def main():
    cmd_args = get_cmd_args()

    wenku = MaYiWenKu(data_dir=cmd_args.data_dir)
    if cmd_args.url:
        if cmd_args.max_page:
            max_page = int(cmd_args.max_page)
        else:
            max_page = None
        try:
            image_dir = wenku.get_document(cmd_args.url, max_page=max_page)
            wenku.images2pdf(image_dir)
        except Exception as e:
            wenku.log(e)
    return


if __name__ == "__main__":
    main()
    # 测试
    # wenku = MaYiWenKu()
    # image_dir = wenku.get_document("http://www.mayiwenku.com/p-4595100.html")
    # wenku.images2pdf(image_dir)
