BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Time Distribution Statistics</title>
    <!-- 引入ECharts -->
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <!-- 引入Bootstrap样式 -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- 引入Font Awesome图标 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
            --accent-color: #7209b7;
            --light-color: #f8f9fa;
            --dark-color: #212529;
            --success-color: #4cc9f0;
            --warning-color: #f72585;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fb;
            color: #333;
            padding-top: 20px;
        }
        
        .dashboard-header {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 25px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        .card {
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border: none;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            margin-bottom: 20px;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
        }
        
        .card-header {
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            color: white;
            border-top-left-radius: 12px !important;
            border-top-right-radius: 12px !important;
            font-weight: 600;
        }
        
        .control-panel {
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            margin-bottom: 25px;
        }
        
        .chart-container {
            height: 400px;
            min-height: 400px;
            background-color: white;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        
        .stats-card {
            text-align: center;
            padding: 20px;
        }
        
        .stats-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary-color);
            margin: 10px 0;
        }
        
        .stats-label {
            font-size: 1rem;
            color: #6c757d;
            font-weight: 500;
        }
        
        .stats-icon {
            font-size: 2rem;
            color: var(--accent-color);
            margin-bottom: 10px;
        }
        
        .time-controls {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
            border-radius: 8px;
            padding: 8px 20px;
            font-weight: 500;
        }
        
        .btn-primary:hover {
            background-color: var(--secondary-color);
            border-color: var(--secondary-color);
            transform: translateY(-2px);
        }
        
        .form-control, .form-select {
            border-radius: 8px;
            padding: 10px 15px;
            border: 1px solid #ddd;
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
        }
        
        .form-control:focus, .form-select:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 0.25rem rgba(67, 97, 238, 0.25);
        }
        
        .nav-tabs .nav-link {
            border-radius: 8px;
            margin-right: 5px;
            font-weight: 500;
            color: #6c757d;
            padding: 10px 20px;
        }
        
        .nav-tabs .nav-link.active {
            background-color: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(255, 255, 255, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            border-radius: 12px;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        footer {
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9rem;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 标题区域 -->
        <div class="dashboard-header">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1><i class="fas fa-chart-bar me-3"></i>Time Distribution Statistics</h1>
                    <p class="mb-0">Visualize data distribution based on archived time</p>
                </div>
                <div class="col-md-4 text-end">
                    <i class="fas fa-database fa-3x opacity-75"></i>
                </div>
            </div>
        </div>

        <!-- 控制面板 -->
        <div class="control-panel">
            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="timeRange" class="form-label fw-bold">Time Range</label>
                        <div class="time-controls">
                            <input type="datetime-local" id="startTime" class="form-control">
                            <span class="align-self-center">to</span>
                            <input type="datetime-local" id="endTime" class="form-control">
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="mb-3">
                        <label for="timeUnit" class="form-label fw-bold">Time Unit</label>
                        <select id="timeUnit" class="form-select">
                            <option value="hourly">Hourly</option>
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="mb-3">
                        <label class="form-label fw-bold invisible">Action</label>
                        <button id="fetchData" class="btn btn-primary w-100">
                            <i class="fas fa-sync-alt me-2"></i>Update Chart
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- 统计卡片 -->
        <div class="row">
            <div class="col-md-4">
                <div class="card stats-card">
                    <div class="stats-icon">
                        <i class="fas fa-layer-group"></i>
                    </div>
                    <div class="stats-value" id="totalCount">0</div>
                    <div class="stats-label">Total Records</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card stats-card">
                    <div class="stats-icon">
                        <i class="fas fa-clock"></i>
                    </div>
                    <div class="stats-value" id="timeRangeValue">0</div>
                    <div class="stats-label">Time Range</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card stats-card">
                    <div class="stats-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="stats-value" id="averageValue">0</div>
                    <div class="stats-label">Average Per Period</div>
                </div>
            </div>
        </div>

        <!-- 图表区域 -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-chart-area me-2"></i>
                        Data Distribution Chart
                    </div>
                    <div class="card-body position-relative">
                        <div id="chartContainer" class="chart-container"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 底部信息 -->
        <footer>
            <p>© 2023 Data Visualization Dashboard | Built with Flask, MongoDB & ECharts</p>
        </footer>
    </div>

    <script>
        // 初始化ECharts实例
        const chartDom = document.getElementById('chartContainer');
        const myChart = echarts.init(chartDom);
        
        // 设置默认图表选项
        const defaultOption = {
            title: {
                text: 'Data Distribution by Time',
                left: 'center',
                textStyle: {
                    fontSize: 18,
                    fontWeight: 'bold'
                }
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
                borderColor: '#ddd',
                textStyle: {
                    color: '#333'
                },
                formatter: function(params) {
                    return `${params[0].axisValue}<br/>${params[0].marker} Count: ${params[0].data}`;
                }
            },
            xAxis: {
                type: 'category',
                name: 'Time',
                nameLocation: 'middle',
                nameGap: 30,
                axisLine: {
                    lineStyle: {
                        color: '#666'
                    }
                },
                axisLabel: {
                    rotate: 45
                }
            },
            yAxis: {
                type: 'value',
                name: 'Count',
                nameLocation: 'middle',
                nameGap: 40,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: '#666'
                    }
                },
                splitLine: {
                    lineStyle: {
                        type: 'dashed',
                        color: '#ddd'
                    }
                }
            },
            series: [{
                type: 'bar',
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#4361ee' },
                        { offset: 1, color: '#3a0ca3' }
                    ])
                },
                emphasis: {
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#7209b7' },
                            { offset: 1, color: '#4cc9f0' }
                        ])
                    }
                },
                data: []
            }],
            grid: {
                left: '5%',
                right: '5%',
                bottom: '15%',
                top: '15%',
                containLabel: true
            }
        };
        
        myChart.setOption(defaultOption);
        
        // 设置默认时间范围（最近24小时）
        const now = new Date();
        const oneDayAgo = new Date(now.getTime() - (24 * 60 * 60 * 1000));
        
        document.getElementById('startTime').value = formatDateTime(oneDayAgo);
        document.getElementById('endTime').value = formatDateTime(now);
        
        // 格式化日期时间为YYYY-MM-DDTHH:MM
        function formatDateTime(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            
            return `${year}-${month}-${day}T${hours}:${minutes}`;
        }
        
        // 从API获取数据
        async function fetchData() {
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;
            const timeUnit = document.getElementById('timeUnit').value;
            
            // 显示加载状态
            showLoading();
            
            try {
                const apiUrl = `/statistics/intelligence_distribution/${timeUnit}?start=${startTime}&end=${endTime}`;
                const response = await fetch(apiUrl);
                const data = await response.json();
                
                // 处理数据并更新图表
                processData(data, timeUnit);
                
                // 获取摘要信息
                await fetchSummary(startTime, endTime);
            } catch (error) {
                console.error('Error fetching data:', error);
                alert('Failed to fetch data. Please check console for details.');
            } finally {
                // 隐藏加载状态
                hideLoading();
            }
        }
        
        // 显示加载状态
        function showLoading() {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = '<div class="spinner"></div>';
            chartDom.appendChild(overlay);
            
            document.getElementById('fetchData').disabled = true;
            document.getElementById('fetchData').innerHTML = '<i class="fas fa-circle-notch fa-spin me-2"></i>Loading...';
        }
        
        // 隐藏加载状态
        function hideLoading() {
            const overlay = chartDom.querySelector('.loading-overlay');
            if (overlay) {
                chartDom.removeChild(overlay);
            }
            
            document.getElementById('fetchData').disabled = false;
            document.getElementById('fetchData').innerHTML = '<i class="fas fa-sync-alt me-2"></i>Update Chart';
        }
        
        // 处理数据并更新图表
        function processData(data, timeUnit) {
            const xAxisData = [];
            const seriesData = [];
            
            // 根据时间单位处理数据
            data.forEach(item => {
                let timeLabel = '';
                
                switch(timeUnit) {
                    case 'hourly':
                        timeLabel = `${item._id.year}-${item._id.month}-${item._id.day} ${item._id.hour}:00`;
                        break;
                    case 'daily':
                        timeLabel = `${item._id.year}-${item._id.month}-${item._id.day}`;
                        break;
                    case 'weekly':
                        timeLabel = `Week ${item._id.week}, ${item._id.year}`;
                        break;
                    case 'monthly':
                        timeLabel = `${item._id.year}-${item._id.month}`;
                        break;
                }
                
                xAxisData.push(timeLabel);
                seriesData.push(item.count);
            });
            
            // 更新图表
            myChart.setOption({
                xAxis: {
                    data: xAxisData
                },
                series: [{
                    data: seriesData
                }]
            });
        }
        
        // 获取摘要信息
        async function fetchSummary(startTime, endTime) {
            try {
                const apiUrl = `/statistics/intelligence_distribution/summary?start=${startTime}&end=${endTime}`;
                const response = await fetch(apiUrl);
                const data = await response.json();
                
                document.getElementById('totalCount').textContent = data.total_count.toLocaleString();
                document.getElementById('timeRangeValue').textContent = formatDateRange(data.time_range.start, data.time_range.end);
                
                // 计算每个时间段的平均值
                const timeDiff = new Date(data.time_range.end) - new Date(data.time_range.start);
                const daysDiff = timeDiff / (1000 * 60 * 60 * 24);
                
                if (daysDiff > 0) {
                    const avgValue = (data.total_count / daysDiff).toFixed(1);
                    document.getElementById('averageValue').textContent = avgValue;
                }
            } catch (error) {
                console.error('Error fetching summary:', error);
            }
        }
        
        // 格式化日期范围显示
        function formatDateRange(start, end) {
            const startDate = new Date(start);
            const endDate = new Date(end);
            
            const options = { year: 'numeric', month: 'short', day: 'numeric' };
            return `${startDate.toLocaleDateString(undefined, options)} - ${endDate.toLocaleDateString(undefined, options)}`;
        }
        
        // 添加事件监听器
        document.getElementById('fetchData').addEventListener('click', fetchData);
        
        // 初始加载数据
        fetchData();
        
        // 响应窗口大小变化
        window.addEventListener('resize', function() {
            myChart.resize();
        });
    </script>
</body>
</html>
"""


def get_intelligence_statistics_page() -> str:
    return BASE_TEMPLATE
