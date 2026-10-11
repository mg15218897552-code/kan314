# coding=utf-8
# MissAV 专线 TVBox 插件 —— 纯匿名版
# 不含任何个人账号信息: 无 TG 账号 / 无 UID / 无设备指纹 / 无写死令牌
# 每次自动向服务端开一个匿名号拿令牌, 自动缓存 + 失效自动续, 不需要手填
# 纯标准库实现, 自带重试 + 证书兜底, TVBox(四壳/白壳/OK壳) 通用
import json
import os
import ssl
import time

try:
    import requests
except Exception:
    requests = None
try:
    import urllib.request as _urlreq
    import urllib.parse as _urlparse
    import urllib.error as _urlerr
except Exception:
    _urlreq = None
    _urlparse = None
    _urlerr = None

BASE = "https://missav.ws.ystv.top"
UA = "okhttp/3.12.0"
TIMEOUT = 30

# 想手动指定令牌就填这里(留空 = 全自动开号)
TOKEN = ""

# 令牌缓存位置(按顺序试, 第一个能写的就用)
_CACHE_PATHS = [
    "/sdcard/missav_token.txt",
    os.path.join(os.path.expanduser("~"), ".missav_token"),
    os.path.join(os.getcwd(), "missav_token.txt"),
]

_S = {"tok": "", "ts": 0.0}


# ---------------- HTTP 层 ----------------
class AuthError(Exception):
    """服务端说令牌无效 —— 触发自动换令牌"""
    pass


def _ssl_ctx():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None


def _raw(url, timeout=TIMEOUT):
    """取回文本; 401/403 抛 AuthError, 其它异常原样抛"""
    headers = {"User-Agent": UA, "Accept": "*/*"}
    last = None
    for attempt in range(3):
        try:
            if requests is not None:
                r = requests.get(url, timeout=timeout, headers=headers, verify=False)
                r.encoding = "utf-8"
                if r.status_code in (401, 403):
                    raise AuthError(r.text[:200])
                if r.status_code >= 400:
                    raise RuntimeError("HTTP %s" % r.status_code)
                return r.text
            if _urlreq is None:
                raise RuntimeError("当前 Python 环境没有可用的网络库")
            req = _urlreq.Request(url, headers=headers)
            try:
                resp = _urlreq.urlopen(req, timeout=timeout, context=_ssl_ctx())
            except TypeError:                      # 老版本签名不带 context
                resp = _urlreq.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", "replace")
        except AuthError:
            raise
        except Exception as e:
            last = e
            if _urlerr is not None and isinstance(e, _urlerr.HTTPError) and e.code in (401, 403):
                raise AuthError(str(e))
            if attempt < 2:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise RuntimeError("请求失败: %s" % last)


# ---------------- 令牌:自动开号 + 缓存 ----------------
def _read_cache():
    for p in _CACHE_PATHS:
        try:
            with open(p, "r") as fh:
                t = fh.read().strip()
            if t:
                return t
        except Exception:
            continue
    return ""


def _write_cache(tok):
    for p in _CACHE_PATHS:
        try:
            d = os.path.dirname(p)
            if d and not os.path.isdir(d):
                continue
            with open(p, "w") as fh:
                fh.write(tok)
            return True
        except Exception:
            continue
    return False


def _register():
    """调公开接口自动开号: 返回 {tok, u, p}; 失败返回空 dict"""
    if _urlparse is None:
        return {}
    url = BASE + "/api/tvbox/reg?ts=" + str(int(time.time() * 1000))
    try:
        j = json.loads(_raw(url))
    except Exception:
        return {}
    tok = str(j.get("tok") or "")
    if tok:
        _S["tok"] = tok
        _S["ts"] = time.time()
        _write_cache(tok)
    return j


def _token(force=False):
    """拿一个可用令牌: 手填 > 缓存 > 自动开号"""
    if TOKEN:
        return TOKEN
    if force:
        _S["tok"] = ""
    if _S["tok"] and not force:
        return _S["tok"]
    tok = "" if force else _read_cache()
    if tok:
        _S["tok"] = tok
        _S["ts"] = time.time()
        return tok
    _register()
    return _S["tok"]


def _api(path, **kw):
    """调接口; 遇到 401 自动换令牌重试一次"""
    if _urlparse is None:
        return {}
    for i in range(2):
        tok = _token(force=(i > 0))
        parts = []
        for k in kw:
            v = kw[k]
            if v is None or v == "":
                continue
            parts.append("%s=%s" % (k, _urlparse.quote(str(v))))
        if tok:
            parts.append("t=" + tok)
        url = BASE + path + ("?" + "&".join(parts) if parts else "")
        try:
            return json.loads(_raw(url))
        except AuthError:
            if i == 0:
                continue
            return {"error": "unauthorized", "msg": "自动开号失败, 稍后重试"}
        except Exception as e:
            return {"error": "network", "msg": str(e)}
    return {}


def _diag_card(title, detail):
    """出错时给一张卡片, 电视上直接能看到原因, 不再是一片空白"""
    return [{
        "vod_id": "err:msg",
        "vod_name": title,
        "vod_pic": "",
        "vod_remarks": "",
        "vod_content": str(detail)[:500],
    }]


# ---------------- TVBox 接口 ----------------
class Spider(object):
    def getName(self):
        return "MissAV 专线"

    def init(self, extend=""):
        # extend 可留空; 也可以直接塞一个令牌, 或 {"token": "xxx"}
        global TOKEN
        if extend:
            s = str(extend).strip()
            if s.startswith("{"):
                try:
                    TOKEN = str(json.loads(s).get("token") or "")
                except Exception:
                    pass
            elif "://" not in s:
                TOKEN = s
        if not TOKEN and not _S["tok"]:
            _register()
        if requests is None:
            pass
        print("[MissAV] 匿名模式 | 本地不保存任何账号信息 | 令牌: %s" % ("已就绪" if _token() else "自动开号失败"))
        print("[MissAV] 节点: %s" % BASE)

    def homeContent(self, filter):
        j = _api("/api/tvbox/home")
        cls = j.get("class") or []
        if not cls:
            return {"class": [{"type_id": "hot:latest", "type_name": "🔥 最新上架"}],
                    "filters": {}}
        return {"class": cls, "filters": j.get("filters", {})}

    def homeVideoContent(self):
        r = self.categoryContent("hot:latest", 1, False, {})
        return {"list": r.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        j = _api("/api/tvbox/list", cid=tid, pg=pg)
        lst = j.get("list") or []
        if not lst:
            return {"list": _diag_card("⚠️ 这个分类没拿到数据",
                                       j.get("msg") or j.get("error") or "服务端返回空列表"),
                    "page": pg, "pagecount": 1, "limit": 48, "total": 0}
        return {
            "list": lst,
            "page": j.get("page", pg),
            "pagecount": j.get("pagecount", 1),
            "limit": j.get("limit", 48),
            "total": j.get("total", 0),
        }

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if len(ids) else ""
        else:
            vid = str(ids)
        vid = vid.split("@")[0].strip()
        if not vid:
            return {"list": []}
        j = _api("/api/tvbox/detail", id=vid)
        lst = j.get("list") or []
        if not lst:
            return {"list": _diag_card("⚠️ 详情没拿到数据",
                                       j.get("msg") or j.get("error") or vid)}
        for v in lst:
            if v.get("vod_pic") and not str(v["vod_pic"]).startswith("http"):
                v["vod_pic"] = BASE + "/img/" + str(v.get("vod_id", "")) + "?s=big"
        return {"list": lst}

    def searchContent(self, key, quick, pg=1):
        j = _api("/api/tvbox/search", wd=key, pg=pg)
        lst = j.get("list") or []
        if not lst:
            return {"list": _diag_card("🔍 没搜到「%s」" % key,
                                       j.get("msg") or j.get("error") or "换个关键词试试"),
                    "page": pg, "pagecount": 1}
        return {"list": lst, "page": j.get("page", pg),
                "pagecount": j.get("pagecount", 1)}

    def playerContent(self, flag, id, vipFlags):
        rid, q = (str(id).split("@", 1) + [""])[:2] if "@" in str(id) else (str(id), "")
        j = _api("/api/tvbox/play", id=rid, q=q)
        url = j.get("url") or ""
        if not url:
            return {"parse": 0, "url": "", "header": {},
                    "format": "application/vnd.apple.mpegurl"}
        return {
            "parse": 0,
            "url": url,
            "header": j.get("header") or {"User-Agent": UA, "Referer": BASE + "/"},
        }


# ---------------- 本机自检(不装进壳里也能跑) ----------------
if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("")
    print("[1] 首页分类")
    hc = sp.homeContent(False)
    for c in hc.get("class", [])[:8]:
        print("    ", c.get("type_id"), c.get("type_name"))
    print("     共 %d 个分类" % len(hc.get("class", [])))
    print("[2] 最新上架 第1页")
    r = sp.categoryContent("hot:latest", 1, False, {})
    print("     条数 %s  总页数 %s  总数 %s" % (len(r.get("list", [])), r.get("pagecount"), r.get("total")))
    for v in r.get("list", [])[:3]:
        print("     -", v.get("vod_id"), v.get("vod_name"))
    print("[3] 翻页(第2页)")
    r2 = sp.categoryContent("hot:latest", 2, False, {})
    print("     第2页条数 %s  (为0说明翻页没生效)" % len(r2.get("list", [])))
    print("[4] 详情")
    vid = (r.get("list") or [{}])[0].get("vod_id", "")
    d = sp.detailContent([vid]).get("list", [])
    if d:
        print("     ", d[0].get("vod_id"), "|", d[0].get("vod_name"))
        print("     播放字段:", d[0].get("vod_play_url"))
    print("[5] 取播放地址")
    pid = ((d[0].get("vod_play_url") or "").split("$")[-1]) if d else ""
    if pid:
        p = sp.playerContent("", pid, [])
        print("     ", (p.get("url") or "(空)")[:110])
    print("")
    print("5 项都有内容 = 通了; 哪一项空就截图给我。")
