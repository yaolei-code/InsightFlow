from sqlalchemy import select
from .db import Session
from . import models as m
from .discovery import canonical_url

ALIASES={'Simate':['Sinfra'],'NVIDIA':['英伟达'],'智元机器人':['智元','AGIBOT'],'北京人形机器人创新中心':['北京人形','X-Humanoid'],'逐际动力':['LimX Dynamics','LimX'],'银河通用':['GALBOT'],'Physical Intelligence':['Physical Intelligence','openpi'],'Figure AI':['Figure'],'1X':['1X Technologies'],'宇树科技':['宇树','Unitree'],'优必选':['UBTECH']}

def main():
    with Session() as db:
        entries=[('机器人大讲堂','https://www.leaderobot.com/','industry_media',None),('机器人新闻网','https://www.robotnews.com.cn/','industry_media',None),('中国机器人产业发展联盟','https://www.cdra.com.cn/news','industry_media',None),('具身纪','https://www.jushenji.com/','industry_media',None),('具身之家','https://www.jushenhome.com/','industry_media',None)]
        for c in db.scalars(select(m.Company)):
            if c.official_url:entries.append((c.name+' 官方入口',c.official_url,'official_website',c.id))
            for alias in ALIASES.get(c.name,[]):
                if not db.scalar(select(m.CompanyAlias).where(m.CompanyAlias.alias==alias)):db.add(m.CompanyAlias(company_id=c.id,alias=alias))
        for name,url,kind,cid in entries:
            url=canonical_url(url)
            if not db.scalar(select(m.DiscoverySeed).where(m.DiscoverySeed.url==url)):db.add(m.DiscoverySeed(name=name,url=url,source_type=kind,company_id=cid))
        db.commit()

if __name__=='__main__':main()
