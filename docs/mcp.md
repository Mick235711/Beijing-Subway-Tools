# MCP 协议与接口定义文档

本文档定义了北京地铁工具集 (Beijing Subway Tools) 提供的 MCP (Model Context Protocol) 服务能力、工具接口规范及数据交互格式。

时刻表这类直接打印的话可能不太便于client解析，使用了json返回。其他比较麻烦的部分直接复用现有的cli交互逻辑来返回了。

## 部署方式

### 1. 本地 Stdio 模式 (推荐)
适用于 Claude Desktop, Cursor 等本地客户端。无需手动启动服务，客户端会自动管理。

**VS Code客户端配置示例:**

```json
{
    "servers": {
        "beijing-subway": {
            "type": "stdio",
            "command": "python3",
            "args": [
                "path/to/Beijing-Subway-Tools/src/mcp/server.py"
            ],
            "env": {
                "PYTHONPATH": "path/to/Beijing-Subway-Tools"
            }
        }
    }
}
```

### 2. HTTP 模式 (远程访问)
适用于需要通过 HTTP 访问或远程部署的场景。

**启动命令:**

```bash
# 启动服务监听 8101 端口
fastmcp run src/mcp/server.py --transport http --host 0.0.0.0 --port 8101 --path /mcp
# OR
python3 src/mcp/server.py --http [--host HOST] [--port PORT] [--path PATH]

# 使用 PM2 常驻后台:
pm2 start "./.venv/bin/fastmcp run src/mcp/server.py --transport http --host 0.0.0.0 --port 8101 --path /mcp" --name "bjsubway-mcp"
```

**客户端配置示例:**

```json
{
  "mcpServers": {
    "beijing-subway": {
      "url": "http://<server-ip>:8101/mcp"
    }
  }
}
```

## 工具接口定义

### 1. 基础元数据 (Metadata)

#### 1.1 获取线路列表 (`get_lines`)
获取当前城市所有可用的地铁线路名称。

**输入参数:** 无

**输出参数:**
- `list[str]`: 线路名称列表，如 `['1号线', '2号线', ...]`

#### 1.2 获取车站列表 (`get_stations`)
获取车站列表，支持按线路筛选。

**输入参数:**

| 参数名         | 类型     | 必填 | 说明                               |
|:------------|:-------|:---|:---------------------------------|
| `line_name` | string | 否  | 指定线路名称。若提供，则返回该线路的所有车站；否则返回所有车站。 |

**输出参数:**
- `list[str]`: 车站名称列表。

#### 1.3 获取线路方向 (`get_directions`)
获取线路的运行方向列表。

**输入参数:**

| 参数名             | 类型     | 必填 | 说明      |
|:----------------|:-------|:---|:--------|
| `line_name`     | string | 否  | 线路名称。   |
| `start_station` | string | 否  | 起点车站名称。 |
| `end_station`   | string | 否  | 终点车站名称。 |

**说明:**
- 若仅指定 `line_name`，返回该线路所有定义的方向。
- 若指定 `start_station` 和 `end_station`，系统将尝试推断从起点到终点的方向。

**输出参数:**
- `list[str]`: 方向名称列表，如 `['上行', '下行']` 或 `['内环', '外环']`。

---

### 2. 时刻表查询 (Timetable)

#### 2.1 查询车站时刻表 (`get_station_timetable`)
查询指定车站的列车到发时刻信息。

**输入参数:**

| 参数名            | 类型      | 必填 | 默认值  | 说明                   |
|:---------------|:--------|:---|:-----|:---------------------|
| `station_name` | string  | 是  | -    | 车站名称，如 '西直门'         |
| `date`         | string  | 是  | -    | 查询日期，格式 'YYYY-MM-DD' |
| `line_name`    | string  | 否  | null | 线路名称，支持模糊匹配          |
| `direction`    | string  | 否  | null | 线路方向标识               |
| `destination`  | string  | 否  | null | 终点站名称，可用于自动匹配方向      |
| `query_time`   | string  | 否  | null | 查询起始时间，格式 'HH:MM'    |
| `count`        | integer | 否  | 5    | 限制返回的列车数量            |

**输出参数:**
返回包含车站信息及按线路、方向分组的时刻表对象；找不到车站时返回 `{ "error": "..." }`。

```json
{
  "station": "西直门",
  "date": "2023-10-27",
  "lines": [
    {
      "line": "13号线",
      "directions": [
        {
          "direction": "东行",
          "date_group": "工作日",
          "trains": [
            {
              "train_code": "1001",
              "departure_time": "08:05",
              "is_last_train": false,
              "routes": ["全程车"]
            }
          ]
        }
      ]
    }
  ]
}
```

#### 2.2 获取列车详细信息 (`get_train_detailed_info`)
获取特定车次的完整运行计划，包括沿途各站的到发时间。

**输入参数:**

| 参数名            | 类型     | 必填 | 说明                   |
|:---------------|:-------|:---|:---------------------|
| `line_name`    | string | 是  | 线路名称                 |
| `date`         | string | 是  | 查询日期，格式 'YYYY-MM-DD' |
| `train_code`   | string | 否  | 列车车次号/标识             |
| `station_name` | string | 否  | 辅助定位列车的车站名           |
| `approx_time`  | string | 否  | 辅助定位列车的大致时间 (HH:MM)  |

**说明:**
- 必须提供 `train_code` 或者 (`station_name` + `approx_time`) 来唯一定位一趟列车。

**输出参数:**
- `string`: 纯文本格式的列车运行明细（调用现有 pretty_print，含区间耗时/里程/速度）。未找到列车时返回如 `"Error: Train not found"`。

```
13号线 东行 全程车 [6B] 西直门 08:00 -> 东直门 08:25 (25min, 27.1km, 65.1km/h)

西直门 08:00
(3min, 2.50km, 50.00km/h)
大钟寺 08:03 (+3min, +2.50km)
...
东直门 08:25 (+25min, +27.10km)
```

---

### 3. 路径规划 (Planning)

#### 3.1 查询换乘指标 (`get_transfer_metrics`)
查询特定车站内的换乘耗时数据。

**输入参数:**

| 参数名            | 类型     | 必填 | 说明     |
|:---------------|:-------|:---|:-------|
| `station_name` | string | 是  | 换乘车站名称 |
| `from_line`    | string | 否  | 来源线路   |
| `to_line`      | string | 否  | 目标线路   |

**输出参数:**
- `list[Dict]`: 换乘信息列表。

```json
[
  {
    "station": "西直门",
    "from_line": "2号线",
    "to_line": "13号线",
    "transfer_time_minutes": 5,
    "is_virtual_transfer": false,
    "note": "..."
  }
]
```

#### 3.2 路径规划 (`plan_journey`)
计算两个站点之间的最佳路线。

**输入参数:**

| 参数名              | 类型      | 必填 | 默认值        | 说明                                                                                          |
|:-----------------|:--------|:---|:-----------|:--------------------------------------------------------------------------------------------|
| `start_station`  | string  | 是  | -          | 起点站                                                                                         |
| `end_station`    | string  | 是  | -          | 终点站                                                                                         |
| `date`           | string  | 是  | -          | 出发日期 'YYYY-MM-DD'                                                                           |
| `departure_time` | string  | 否  | null       | 出发时间 'HH:MM'，未提供时默认使用当前本地时间                                                                 |
| `strategy`       | string  | 否  | 'min_time' | 规划策略，仅支持 'min_time' / 'min_transfer'                                                        |
| `num_paths`      | integer | 否  | 1          | 仅在 strategy='min_time' 生效，返回前 num_paths 条最短路线，num_paths>=1；strategy='min_transfer' 始终返回 1 条 |

**输出参数:**
- `string`: 格式化的文本路线描述，包含换乘指引和预计耗时。
