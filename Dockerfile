FROM ubuntu
MAINTAINER tutu 357136202@qq.com

WORKDIR /root/Desktop
RUN apt-get update
RUN apt-get install -y python python-pip

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY ./mysite /root/Desktop
COPY ./run.sh /root/Desktop
RUN chmod +x /root/Desktop/run.sh

ENTRYPOINT ["./run.sh"]
EXPOSE 5000