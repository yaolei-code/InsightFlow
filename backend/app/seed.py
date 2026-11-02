from sqlalchemy import select
from .db import Session
from .models import Product, Source

def main():
    with Session() as db:
        for name,company,category,url,kind in [
            ('Simate Sinfra','Simate','机器人研发基础设施','https://mate-robot.cn/research/sinfra/','official_website'),
            ('FluxVLA Engine','FluxVLA','VLA 工程平台','https://github.com/FluxVLA/FluxVLA','github_repository'),
            ('NVIDIA Isaac','NVIDIA','机器人生态平台','https://developer.nvidia.com/isaac','official_website')]:
            if db.scalar(select(Product).where(Product.official_url==url)):
                continue
            p=Product(name=name,company=company,category=category,official_url=url)
            db.add(p); db.flush()
            db.add(Source(product_id=p.id,url=url,source_type=kind))
        db.commit()

if __name__=='__main__': main()
