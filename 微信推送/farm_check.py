#!/usr/bin/python
#-*- coding:utf-8 -*-

# *****************************************************************************
# 版本更新记录：
# -----------------------------------------------------------------------------
#
# 版本 1.0.0 ， 最后更新于 2016-09-29， by guan.huang
#
#工作流程 ：将temp目录下各个场站下面的健康文件和告警文件解析并将内容推送给配置文档里相应的人
#
# *****************************************************************************
# =============================================================================
# 导入外部模块
# =============================================================================
import datetime
import hashlib
import json
import os
import re
import requests
import sys
import time
import ConfigParser
import smtplib
from email.MIMEText import MIMEText
# =============================================================================
# 常量定义
# =============================================================================
cloud_dir = '../ftproot/'
app_code = 'om' # 申请到的推送代码
template_id1 = "ixiONAURGHc_Oeb7W6gRWX5Xk9yCRcVOltlK7Sibo-c" #健康文件模板
template_id2 = "7bV6vudOZRCp5liyzowBrWvc1hIE1Wc-ExZBj2e4CEY" #告警文件模板
cfgfile = '../config/cloud_check.cfg'   #场站配置文件
host = 'smtp.qq.com'       #用来发邮件的邮箱信息
user = '3520307950@qq.com'
passward = 'qnqnxtwavshncjgf'
# ==============================================================================
#ConfigParser只能返回小写，继承重写optionxform返回区别大小写
# ==============================================================================  
class MyConfigParser(ConfigParser.ConfigParser):
    def __init__(self,defaults=None):
        ConfigParser.ConfigParser.__init__(self,defaults=None)
    def optionxform(self,optionstr):
        return optionstr  

# ==============================================================================
# 微信推送函数
# ==============================================================================       
class WechatPush(object):
    def __init__(self, app_code):
        self._app_code = app_code
        self.data = {}

    def getCurrentAccessToken(self):
        # 向中控服务器请求access_token
        # 请求URL示例: http://weixin.token.hezongyun.com/access_token?
        # code=f73d3f0f5b9935bf4b8277e4ae1fff9a
        #
        # 参数 code 的生成规则:
        #     UTC时间当日零点的时间戳，加上分配给使用者的代码，然后MD5加密，
        #     得到32位字符串

        md5_input = '%d%s' % (
            int(time.time()) / 86400 * 86400,
            self._app_code,
        )
        md5_output = hashlib.md5(md5_input).hexdigest()
        url = 'http://weixin.token.hezongyun.com/access_token?code={0}'.format(
            md5_output
        )    
        try:
            token = requests.get(url).text
        except Exception:
            token = ''
        #url2 ='https://api.weixin.qq.com/cgi-bin/template/get_all_private_template?access_token=' + token
       # print requests.get(url2).text
        return token

    def do_push(self,openids,template_id):
        self.token = self.getCurrentAccessToken()
        post_url = 'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token=' + self.token
        try:
            for openid in openids:
                post_data = {
                    'touser': openid, 
                    'template_id':template_id, 
                     'url':'', 
                    'topcolor':'#FF0000',
                    'data':self.data
                }
                response = requests.request(
                    method='post',
                    url=post_url,
                    data=json.dumps(post_data, ensure_ascii=False).encode('utf-8')
                    ).json()

                if response[u"errcode"] != 0:
                    print 'Error code %d is returned while sending message.' % response[u"errcode"]
                    raise Exception
                print 'Message is sent to %s.' % openid
            return True   
        except Exception,e:
            print 'Failed to send message.',e
            return False

            
    def parse_empty_file(self,farm_name,hz_data,openids,template_id):
         #处理没有收到健康文件情况
         #返回微信推送data和邮箱推送hz_data
        self.data['remark'] = {}
        self.data['first'] ={}
        self.data['remark']['value'] = u'场站没有健康文件'
        self.data['remark']['color'] = "#173177"
        self.data['first']['value'] = farm_name.decode('GBK')
        self.data['first']['color'] = "#173177" 
        hz_data['remark']['value'] += '\n' + self.data['first']['value']
        hz_data['remark']['value'] += ':\n'+ self.data['remark']['value']
        hz_data['remark']['value'] += '\n' + '----------------------------'

        ret = self.do_push(openids,template_id) # 调用推送程序
        return (hz_data,ret)

    def parse_checked_file(self,files,farm_name,hz_data,openids,template_id):
         #处理健康文件
         #返回微信推送data和邮箱推送hz_data
        cf = MyConfigParser()
        cf.read(files)
        for i in ['first', 'keyword1', 'keyword2', 'remark']:
            self.data[i]={}    
        self.data['keyword1']['value'] = time.strftime('%Y-%m-%d')
        self.data['keyword1']['color'] = "#173177"
        self.data['keyword2']['value'] = time.strftime('%H:%M:%S')
        self.data['keyword2']['color'] = "#173177"
        self.data['remark']['value'] = u''
        self.data['remark']['color'] = "#173177"
        self.data['first']['value'] = farm_name.decode('GBK')                  
        self.data['first']['color'] = "#173177"
        for i in cf.sections():
            if i =='push':
                for j in cf.items(i):
                    self.data['remark']['value'] += j[1].split('||')[1].decode('GBK')+'\n'
            else:
                for j in cf.items(i):
                    if j[1].split('||')[0] == '0':
                        self.data['remark']['value'] += j[1].split('||')[1].decode('GBK')+'\n'
        hz_data['remark']['value'] += '\n' + self.data['first']['value']
        hz_data['remark']['value'] += ':\n'+ self.data['remark']['value']
        hz_data['remark']['value'] += '----------------------------'

        ret = self.do_push(openids,template_id) # 调用推送程序
        return (hz_data,ret)

    def parse_warn_file(self,files,farm_name,hz_openid,template_id):
         #处理告警文件
         #返回微信推送data
        cf = MyConfigParser()
        cf.read(files)
        for i in ['first', 'content','occurtime' , 'remark']:
            self.data[i]={}    
        self.data['content']['value'] = u''
        self.data['content']['color'] = "#173177"
        self.data['occurtime']['value'] = time.strftime('%H:%M:%S')
        self.data['occurtime']['color'] = "#173177"
        self.data['first']['value'] = farm_name.decode('GBK')                  
        self.data['first']['color'] = "#173177"
        for i in cf.sections():
            if i =='warn':
                for j in cf.items(i):
                    self.data['content']['value'] += j[1].decode('GBK')+'\n'

        ret = self.do_push(hz_openid,template_id) # 调用推送程序
        return (self.data,ret)

# ==============================================================================
# 邮箱推送函数
# ============================================================================== 
class EmailPush(object):
    def  __init__(self, host,user,passward):       
        self.host = host
        self.user = user
        self.passward = passward
    
    def send_mail(self,p,content):
        self.msg = MIMEText(content)
        self.msg['Subject'] = 'opps电场每日健康信息'
        self.msg['From'] = '风功率预测自动运维' + '<'+ self.user+ '>'
        self.msg['To'] = p
        self.emailconnect()
        
    def emailconnect(self):
        s = smtplib.SMTP_SSL()
        s.connect(self.host)
        s.login(self.user.split('@')[0],self.passward)
        s.sendmail(self.user,self.msg['To'],self.msg.as_string())
        s.close()
        print 'send email successful'
        return True
 
# ==============================================================================
# 主要运行函数
# ============================================================================== 
class PushManage(object):

    def  __init__(self,cfgfile, cloud_dir,template_id1,template_id2):       
        self._cfgfile = cfgfile
        self._cloud_dir = cloud_dir
        self._template_id1 = template_id1
        self._template_id2 = template_id2
        self.parse_config_file()

    def parse_config_file(self):
        cf = MyConfigParser()
        cf.read(self._cfgfile )
        self._check_data = {}
        for i in cf.sections():
            if i =='dtime':
                self._dtime = cf.get('dtime', 'upload_time').split(' ')[0]
            elif i == 'email':
                self._hz_email = cf.options(i) 
            elif i == 'openid':
                pass
            else: 
                self._check_data[i]= cf.items(i)
        
        self.get_push_file()

    def get_dir_list(self):
        #返回指定目录下的子目录
        if self._cloud_dir == '':
            return []
        a = os.listdir(self._cloud_dir)
        b = [x for x in a if os.path.isdir(self._cloud_dir+x)]
        return b 

    def get_push_file(self):
        #根据处理完的健康文件信息以及告警文件信息，分类微信推送以及邮箱推送场站的具体信息
        hz_data = {}
        dirs = self.get_dir_list()
        current_moment = time.strftime('%H:%M:%S', time.localtime(int(time.time())))
        current_moment1 = time.strftime('%H:%M:%S', time.localtime(int(time.time())-120))
        today_time =  time.strftime('%Y%m%d', time.localtime(int(time.time())))
        yesterday_time =  time.strftime('%Y%m%d', time.localtime(int(time.time()) - 86400))

        for i in ['first', 'keyword1', 'keyword2', 'remark']:
            hz_data[i] = {}     # 用于整合多个场信息邮箱推送给合纵运维
        hz_data['remark']['value'] = ''        
        for i in self._check_data.keys():
            checked_openids = []
            warn_openids = []
            farm_code = i.split(':')[0]
            farm_name = i.split(':')[1]
            for j in self._check_data[i]:
                if j[1] == '0' or j[1] == '2':
                    checked_openids.append(j[0])
                if j[1] == '1' or j[1] == '2':
                    warn_openids.append(j[0]) 
            #print checked_openids,farm_code
            #print warn_openids
            if farm_code in dirs: # 开始遍历类似wf_nanliao目录下的文件
                files = []
                checkedfile = 'checked_%s_%s_000000' % (farm_code.split('_')[1],today_time)
                yesterdayfile='checked_%s_%s_000000' % (farm_code.split('_')[1],yesterday_time)
                for file_name in os.listdir(self._cloud_dir+farm_code):
                    ret = False
                    filepath = self._cloud_dir + farm_code + '/' + file_name
                    if re.match(yesterdayfile, file_name):
                        os.remove(filepath)# 删掉昨天的健康文件，避免重复推送昨天信息
                        continue
                    # 告警文件处理
                    if re.match('^warn_%s_\d{8}_\d{6}$' % farm_code.split('_')[1], file_name):
                        if current_moment < '22:00:00' and current_moment > '08:30:00':
                            (data,ret) = wechatpush.parse_warn_file(filepath, farm_name, warn_openids, self._template_id2)
                            if ret:
                                os.remove(filepath)
                    # 健康文件处理       
                    if re.match(checkedfile, file_name) and (current_moment > self._dtime) and (current_moment1 < self._dtime):
                        files.append(file_name)
                        (hz_data,ret) = wechatpush.parse_checked_file(filepath, farm_name, hz_data, checked_openids, self._template_id1)
                        if ret:
                            os.remove(filepath)
                # 当云端没有接收到健康文件时
                if (checkedfile not in files) and (current_moment > self._dtime) and (current_moment1 < self._dtime): 
                    (hz_data,ret) = wechatpush.parse_empty_file(farm_name, hz_data, checked_openids, self._template_id1)

        if (current_moment > self._dtime) and (current_moment1 < self._dtime) and (len(hz_data['remark']['value']) > 0):
            for i in self._hz_email:
                emailpush.send_mail(i,hz_data['remark']['value'].encode('utf-8')) # 邮箱推送


# ==============================================================================
# 业务运行
# ==============================================================================  

if __name__ == '__main__':

    while(1):
        try:
            wechatpush=WechatPush(app_code)
            emailpush = EmailPush(host,user,passward)
            pushmanage = PushManage(cfgfile,cloud_dir,template_id1,template_id2)
            time.sleep(120)
        except Exception,e:
            print e
            time.sleep(120)
            continue             
        except KeyboardInterrupt:
            sys.exit(1)
