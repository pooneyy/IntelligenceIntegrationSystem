基础反向代理配置（A服务器不感知真实客户端）
==

这种配置下，A服务器看到的访问来源IP是B服务器的IP。

```nginx
server {
    listen 80;
    server_name your-domain.com; # B服务器的固定域名

    location / {
        proxy_pass http://your-a-server-dyndns-domain:25000; # A服务器的DDNS地址和端口
        # 此处未设置传递客户端信息的请求头，A服务器只能记录到B服务器的IP
    }
}
```

关键点：此配置仅使用 proxy_pass进行基本转发，A服务器的访问日志中记录的客户端IP将是B服务器的IP。


增强型反向代理配置（A服务器感知真实客户端）
==

这种配置通过在B服务器上修改请求头，将客户端的真实信息传递给A服务器。

```nginx
server {
    listen 80;
    server_name your-domain.com; # B服务器的固定域名

    location / {
        proxy_pass http://your-a-server-dyndns-domain:25000; # A服务器的DDNS地址和端口
        
        # 以下为传递客户端真实信息的关键配置
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr; # 传递客户端真实IP
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; # 记录代理链
        proxy_set_header X-Forwarded-Proto $scheme; # 告知A服务器客户端使用的协议
        # 更多可选配置...
    }
}
```

**关键点解释**

+ proxy_set_header Host $host;：确保A服务器接收到的请求头中的Host字段是客户端原始请求的域名。

+ proxy_set_header X-Real-IP $remote_addr;：将客户端的真实IP地址传递给A服务器。

+ proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;：这是一个标准头部，记录了请求从客户端到服务器经过的所有代理IP。如果请求已包含此头，Nginx会追加当前客户端IP；否则创建它。

+ proxy_set_header X-Forwarded-Proto $scheme;：告知A服务器客户端是使用HTTP还是HTTPS连接到B服务器的。


配置步骤
==

1. **编辑配置文件**：上述配置通常写在Nginx的配置文件中，例如 /etc/nginx/nginx.conf、/etc/nginx/sites-available/default或 /etc/nginx/conf.d/目录下的 .conf文件 。
    > 
    > /etc/nginx/nginx.conf：核心主配置文件。Nginx直接读取此文件启动。
    > /etc/nginx/sites-available/：可用站点配置的仓库。此目录本身不会被直接加载，其中的文件需通过符号链接到sites-enabled/目录来启用
    > sites-enabled/：已启用站点配置的链接目录。 存放指向sites-available/目录中配置文件的符号链接，其中的符号链接文件被nginx.conf主配置文件中的include /etc/nginx/sites-enabled/*;指令加载。
    > /etc/nginx/conf.d/：模块化附加配置的目录。其中的*.conf文件通常被nginx.conf主配置文件中的include /etc/nginx/conf.d/*.conf;指令自动加载。
    > 

2. **检查语法并重载**：配置完成后，使用 sudo nginx -t测试配置文件语法是否正确。确认无误后，使用 sudo systemctl reload nginx或 sudo nginx -s reload重载配置使其生效 。

3. **A服务器的配合**：要使“感知真实客户端”配置生效，A服务器上运行的应用或服务**需要配置为信任并解析**来自B服务器的 X-Forwarded-For、X-Real-IP等头部字段。否则，这些信息会被忽略，A服务器依然会记录B服务器的IP。

4. **防火墙与安全组**：确保B服务器能够访问A服务器的25000端口，并且B服务器监听的端口（如80）对客户端开放。

