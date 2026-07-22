import sys, sqlite3, os, ctypes, re, csv
from datetime import datetime, timedelta
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

CAL_POPUP_STYLE = '''
QCalendarWidget QAbstractItemView:enabled {
    color: #333; background: white;
    selection-background-color: #07c160; selection-color: white; font-size:26px;
}
QCalendarWidget QToolButton { color: #333; font-size:26px; font-weight: bold; }
QCalendarWidget QMenu { color: #333; background: white; }
QCalendarWidget QSpinBox { color: #333; font-size:26px; background: white; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background: #f5f6f8; }
QCalendarWidget QWidget#qt_calendar_weekday { color: #07c160; font-size:22px; font-weight: bold; }
QDateEdit::drop-down, QTimeEdit::drop-down { border: none; width: 28px; }
QDateEdit::down-arrow { image: none; width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 8px solid #07c160; margin-right: 8px; }
QTimeEdit::down-arrow { image: none; width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 8px solid #07c160; margin-right: 8px; }
QDateEdit::up-arrow, QTimeEdit::up-arrow { image: none; }
'''


class ClickableDateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
    def mousePressEvent(self, event):
        QTimer.singleShot(0, self.showPopup)



class DB:
    def __init__(self, name="task_manager.db"):
        bp = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
        self.db_path = os.path.join(bp, name)
        self.conn = sqlite3.connect(self.db_path); self.c = self.conn.cursor()
        self.c.execute("CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL, subject TEXT, intention TEXT, note TEXT, start_time DATETIME, end_time DATETIME, remind_time DATETIME, is_deleted BOOLEAN DEFAULT 0, deleted_time DATETIME, created_time DATETIME DEFAULT CURRENT_TIMESTAMP, category TEXT DEFAULT '库存')")
        self.c.execute("UPDATE tasks SET end_time = REPLACE(end_time,'/','-') WHERE end_time LIKE '%/%'")
        self.c.execute("UPDATE tasks SET start_time = REPLACE(start_time,'/','-') WHERE start_time LIKE '%/%'")
        try: self.c.execute("ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT '库存'")
        except: pass
        self.c.execute("UPDATE tasks SET category='库存' WHERE category IS NULL")
        self.c.execute("CREATE TABLE IF NOT EXISTS intention_users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL, subject TEXT, note TEXT, source TEXT, is_deleted BOOLEAN DEFAULT 0, deleted_time DATETIME, created_time DATETIME DEFAULT CURRENT_TIMESTAMP)")
        self.conn.commit()

    def add_task(self, n, p, s, i, note, st, et, cat="库存"):
        try:
            st_clean = st.replace("/","-")[:16]
            rt = (datetime.strptime(st_clean,"%Y-%m-%d %H:%M") - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        except:
            rt = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        self.c.execute("INSERT INTO tasks(name,phone,subject,intention,note,start_time,end_time,remind_time,category) VALUES(?,?,?,?,?,?,?,?,?)", (n,p,s,i,note,st,et,rt,cat))
        self.conn.commit(); return self.c.lastrowid
    def get_tasks(self, status, s="", cat=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M"); p = f"%{s}%"
        q = "SELECT * FROM tasks WHERE is_deleted=" + ("1" if status=="recycle" else "0")
        if status == "current": q += " AND REPLACE(end_time,'/','-') > ?"
        elif status == "expired": q += " AND REPLACE(end_time,'/','-') <= ?"
        if cat: q += " AND category = ?"
        q += " AND (name LIKE ? OR phone LIKE ? OR subject LIKE ? OR note LIKE ?)"
        order = {"current":"start_time ASC","expired":"end_time DESC","recycle":"deleted_time DESC"}.get(status,"created_time DESC")
        q += " ORDER BY " + order
        params = []
        if status in ("current","expired"): params.append(now)
        if cat: params.append(cat)
        params.extend([p,p,p,p])
        self.c.execute(q, params)
        return self.c.fetchall()

    def delete_task(self, tid, soft=True):
        if soft: self.c.execute("UPDATE tasks SET is_deleted=1, deleted_time=CURRENT_TIMESTAMP WHERE id=?", (tid,))
        else: self.c.execute("DELETE FROM tasks WHERE id=?", (tid,))
        self.conn.commit()

    def restore_task(self, tid):
        self.c.execute("UPDATE tasks SET is_deleted=0, deleted_time=NULL WHERE id=?", (tid,))
        self.conn.commit()

    def update_task(self, tid, n, p, s, i, note, st, et, cat="库存"):
        rt = (datetime.strptime(st,"%Y-%m-%d %H:%M") - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        self.c.execute("UPDATE tasks SET name=?,phone=?,subject=?,intention=?,note=?,start_time=?,end_time=?,remind_time=?,category=? WHERE id=?", (n,p,s,i,note,st,et,rt,cat,tid))
        self.conn.commit()

    def batch_delete(self, ids):
        t = ",".join("?"*len(ids))
        self.c.execute(f"UPDATE tasks SET is_deleted=1, deleted_time=CURRENT_TIMESTAMP WHERE id IN({t})", ids)
        self.conn.commit()

    def batch_restore(self, ids):
        t = ",".join("?"*len(ids))
        self.c.execute(f"UPDATE tasks SET is_deleted=0, deleted_time=NULL WHERE id IN({t})", ids)
        self.conn.commit()

    def add_intention(self, n, p, s, note, src=""):
        self.c.execute("INSERT INTO intention_users(name,phone,subject,note,source) VALUES(?,?,?,?,?)", (n,p,s,note,src))
        self.conn.commit(); return self.c.lastrowid

    def get_intentions(self, deleted=False, s=""):
        q = "SELECT * FROM intention_users WHERE " + ("" if deleted else "is_deleted=0 AND ") + "(name LIKE ? OR phone LIKE ? OR subject LIKE ? OR note LIKE ?) ORDER BY created_time DESC"
        p = f"%{s}%"; self.c.execute(q, (p,p,p,p)); return self.c.fetchall()

    def delete_intention(self, u):
        self.c.execute("UPDATE intention_users SET is_deleted=1, deleted_time=CURRENT_TIMESTAMP WHERE id=?", (u,))
        self.conn.commit()

    def restore_intention(self, u):
        self.c.execute("UPDATE intention_users SET is_deleted=0, deleted_time=NULL WHERE id=?", (u,))
        self.conn.commit()

    def batch_delete_intention(self, ids):
        t = ",".join("?"*len(ids))
        self.c.execute(f"UPDATE intention_users SET is_deleted=1, deleted_time=CURRENT_TIMESTAMP WHERE id IN({t})", ids)
        self.conn.commit()

    def batch_restore_intention(self, ids):
        t = ",".join("?"*len(ids))
        self.c.execute(f"UPDATE intention_users SET is_deleted=0, deleted_time=NULL WHERE id IN({t})", ids)
        self.conn.commit()

    def count_tasks(self, cat=None):
        if cat:
            self.c.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted=0 AND category=?", (cat,))
        else:
            self.c.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted=0")
        return self.c.fetchone()[0]

    def count_today_tasks(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.c.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted=0 AND start_time LIKE ?", (today+"%",))
        return self.c.fetchone()[0]

    def count_current_tasks(self, cat=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if cat:
            self.c.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted=0 AND end_time > ? AND category=?", (now, cat))
        else:
            self.c.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted=0 AND end_time > ?", (now,))
        return self.c.fetchone()[0]

    def count_today_urgent(self):
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.c.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted=0 AND end_time > ? AND start_time LIKE ? AND intention IN (?,?)", (now, today+"%", "高意向", "包来的"))
        return self.c.fetchone()[0]

    def get_task_by_id(self, tid):
        self.c.execute("SELECT * FROM tasks WHERE id=?", (tid,))
        return self.c.fetchone()


class TaskModel(QAbstractTableModel):
    def __init__(self, data=None, ac=False):
        super().__init__(); self._d = data or []; self._c = set(); self._ac = ac
        self._h = ["序号","","创建时间","ID","姓名","电话","意向度","任务类型","开始时间","结束时间","备注"]
        if ac: self._h.append("操作")

    def rowCount(self, p=None): return len(self._d)
    def columnCount(self, p=None): return len(self._h)

    def data(self, idx, role):
        if not idx.isValid(): return None
        r, c = idx.row(), idx.column()
        if c == 0: return str(r+1) if role == Qt.DisplayRole else None
        if c == 1: return Qt.Checked if r in self._c else Qt.Unchecked if role == Qt.CheckStateRole else None
        if self._ac and c == self.columnCount()-1: return "恢复" if role == Qt.DisplayRole else None
        dc = c - 2
        if dc >= len(self._d[r]): return None
        if role == Qt.DisplayRole:
            m = {0:11, 1:0, 2:1, 3:2, 4:4, 5:12, 6:6, 7:7, 8:5}
            db = m.get(dc, dc)
            v = self._d[r][db]
            if v is None: return ""
            v = str(v)
            if db in (6,7,11):
                try: return datetime.strptime(v[:19], "%Y-%m-%d %H:%M:%S" if len(v)>16 else "%Y-%m-%d %H:%M").strftime("%m-%d %H:%M")
                except: return v
            return v
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return None

    def setData(self, idx, v, role):
        if idx.column() == 1 and role == Qt.CheckStateRole:
            r = idx.row()
            if v == Qt.Checked: self._c.add(r)
            else: self._c.discard(r)
            self.dataChanged.emit(idx, idx); return True
        return False

    def flags(self, idx):
        if idx.column() <= 1: return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._ac and idx.column() == self.columnCount()-1: return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def checked(self): return [self._d[r][0] for r in self._c if 0 <= r < len(self._d)]
    def clear_chk(self): self._c.clear()

    def headerData(self, s, o, role):
        if o == Qt.Horizontal and role == Qt.DisplayRole: return self._h[s]
        return None

    def sort(self, col, order):
        if col <= 1: return
        m = {0:11, 1:0, 2:1, 3:2, 4:4, 5:12, 6:6, 7:7, 8:5}
        dc = m.get(col-2, col-2)
        self._d.sort(key=lambda x: str(x[dc] if x[dc] is not None else ""), reverse=order==Qt.DescendingOrder)
        self.layoutChanged.emit()


class IntModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__(); self._d = data or []; self._c = set()
        self._h = ["序号","","创建时间","ID","姓名","电话","科目","备注","来源"]

    def rowCount(self, p=None): return len(self._d)
    def columnCount(self, p=None): return len(self._h)

    def data(self, idx, role):
        if not idx.isValid(): return None
        r, c = idx.row(), idx.column()
        if c == 0: return str(r+1) if role == Qt.DisplayRole else None
        if c == 1: return Qt.Checked if r in self._c else Qt.Unchecked if role == Qt.CheckStateRole else None
        dc = c - 2
        if dc >= len(self._d[r]): return None
        if role == Qt.DisplayRole:
            m = {0:8, 1:0, 2:1, 3:2, 4:3, 5:4, 6:5}
            db = m.get(dc, dc)
            v = self._d[r][db]
            if v is None: return ""
            v = str(v)
            if db == 8:
                try: return datetime.strptime(v[:19], "%Y-%m-%d %H:%M:%S").strftime("%m-%d %H:%M")
                except: return v
            return v
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return None

    def setData(self, idx, v, role):
        if idx.column() == 1 and role == Qt.CheckStateRole:
            r = idx.row()
            if v == Qt.Checked: self._c.add(r)
            else: self._c.discard(r)
            self.dataChanged.emit(idx, idx); return True
        return False

    def flags(self, idx):
        if idx.column() <= 1: return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def checked(self): return [self._d[r][0] for r in self._c if 0 <= r < len(self._d)]
    def clear_chk(self): self._c.clear()

    def headerData(self, s, o, role):
        if o == Qt.Horizontal and role == Qt.DisplayRole: return self._h[s]
        return None

    def sort(self, col, order):
        dc = col - 2
        if dc < 0: return
        self._d.sort(key=lambda x: str(x[dc] if x[dc] is not None else ""), reverse=order==Qt.DescendingOrder)
        self.layoutChanged.emit()


class ReminderDlg(QDialog):
    def __init__(self, task, parent=None):
        super().__init__(parent); self.task = task
        self.setWindowTitle("任务提醒 - 光照超级备忘录")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setModal(True); self.setMinimumSize(380, 260)
        l = QVBoxLayout(self); l.setSpacing(14); l.setContentsMargins(24, 20, 24, 20)
        self.setStyleSheet("QDialog { background: white; border: 2px solid #07c160; border-radius: 10px; }")
        
        hdr = QHBoxLayout()
        icon_lbl = QLabel("🔔"); icon_lbl.setStyleSheet("font-size:26px;")
        hdr.addWidget(icon_lbl)
        title_lbl = QLabel("任务提醒"); title_lbl.setStyleSheet("font-size:24px; font-weight:bold; color:#07c160;")
        hdr.addWidget(title_lbl); hdr.addStretch()
        l.addLayout(hdr)
        
        name = task[1] if task[1] else "未知"
        phone = task[2] if task[2] else ""
        st = task[6] if task[6] else ""
        et = task[7] if task[7] else ""
        subj = task[3] or "-"
        intent = task[4] or "-"
        note = task[5] or "-"
        info = "姓名：" + name + "\n电话：" + phone + "\n时间：" + str(st) + " - " + str(et) + "\n科目：" + subj + "\n意向度：" + intent + "\n备注：" + note
        il = QLabel(info); il.setWordWrap(True)
        il.setStyleSheet("background:#f8f9fb; padding:14px; border-radius:6px; color:#1a1a2e; font-size:24px; line-height:1.5;")
        l.addWidget(il)
        
        b = QHBoxLayout(); b.setSpacing(10)
        k = QPushButton("我知道了"); k.setStyleSheet("QPushButton { background:#07c160; color:#fff; padding:10px 0; border-radius:6px; font-size:26px; font-weight:600; } QPushButton:hover { background:#06ad56; }")
        k.clicked.connect(self.accept)
        r = QPushButton("5分钟后提醒"); r.setStyleSheet("QPushButton { background:#fa5151; color:#fff; padding:10px 0; border-radius:6px; font-size:26px; font-weight:600; } QPushButton:hover { background:#e04848; }")
        r.clicked.connect(lambda: self.done(QDialog.Rejected))
        b.addWidget(k); b.addWidget(r); l.addLayout(b)
        
        try:
            hwnd = int(self.winId())
            class FI(ctypes.Structure): _fields_ = [("cbSize",ctypes.c_uint),("hwnd",ctypes.c_void_p),("dwFlags",ctypes.c_uint),("uCount",ctypes.c_uint),("dwTimeout",ctypes.c_uint)]
            fi = FI(); fi.cbSize = ctypes.sizeof(fi); fi.hwnd = hwnd; fi.dwFlags = 3; fi.uCount = 0; fi.dwTimeout = 0
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(fi))
        except: pass
        self._center()

    def _center(self):
        screen = QDesktopWidget().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)


class TaskForm(QWidget):
    saved = pyqtSignal()
    SUBJECTS = ["首咨", "库存", "二次截杀", "多次截杀", "已付定金"]

    def __init__(self, db, tid=None, parent=None):
        super().__init__(parent); self.db = db; self.tid = tid; self._setup()
        if tid: self.load(tid)

    def _setup(self):
        outer = QVBoxLayout(self); outer.setSpacing(0); outer.setContentsMargins(0, 0, 0, 0)
        card = QWidget(); card.setStyleSheet("background:white; border:1px solid #e0e0e0; border-radius:8px;")
        l = QVBoxLayout(card); l.setSpacing(10); l.setContentsMargins(16, 14, 16, 14)
        
        self.form_title = QLabel("新建任务"); self.form_title.setStyleSheet("font-size:24px; font-weight:bold; color:#1a1a2e; border:none; background:transparent;")
        l.addWidget(self.form_title)
        
        body = QHBoxLayout(); body.setSpacing(20); body.setContentsMargins(0, 8, 0, 8)
        left = QGridLayout(); left.setSpacing(12)
        lbl_sty = "font-size:26px; color:#5a5a7a; border:none; background:transparent; padding-top:6px;"
        inp_sty = "font-size:26px; padding:6px 8px;"
        
        left.addWidget(self._lbl("姓名：", lbl_sty), 0, 0)
        self.name = QLineEdit(); self.name.setPlaceholderText("客户姓名"); self.name.setStyleSheet(inp_sty); left.addWidget(self.name, 0, 1)
        left.addWidget(self._lbl("电话：", lbl_sty), 1, 0)
        self.phone = QLineEdit(); self.phone.setPlaceholderText("联系电话（仅数字）"); self.phone.setStyleSheet(inp_sty)
        self.phone.textChanged.connect(self._filter_phone); left.addWidget(self.phone, 1, 1)
        
        left.addWidget(self._lbl("任务类型：", lbl_sty), 2, 0)
        self.sub = QComboBox(); self.sub.addItems(self.SUBJECTS)
        self.sub.setStyleSheet("QComboBox { selection-background-color:#07c160; selection-color:#fff; font-size:26px; padding:6px 8px; } QComboBox QAbstractItemView { selection-background-color:#07c160; selection-color:#fff; font-size:26px; }"); left.addWidget(self.sub, 2, 1)
        
        left.addWidget(self._lbl("意向度：", lbl_sty), 3, 0)
        self.inq = QComboBox(); self.inq.addItems(["无意向", "低意向", "高意向", "包来的"])
        self.inq.setStyleSheet("QComboBox { selection-background-color:#07c160; selection-color:#fff; font-size:26px; padding:6px 8px; } QComboBox QAbstractItemView { selection-background-color:#07c160; selection-color:#fff; font-size:26px; }"); left.addWidget(self.inq, 3, 1)
        
        left.addWidget(self._lbl("开始时间：", lbl_sty), 4, 0)
        sr = QHBoxLayout(); sr.setSpacing(6)
        self.sd = QDateEdit(); self.sd.setCalendarPopup(True); self.sd.setDate(QDate.currentDate())
        self.sd.setDisplayFormat("MM-dd")
        self.sd.setStyleSheet("font-size:22px; padding:4px 2px;")
        sr.addWidget(self.sd, 3)
        self.st = QTimeEdit(); self.st.setTime(QTime.currentTime()); self.st.setDisplayFormat("HH:mm"); self.st.setStyleSheet("font-size:22px; padding:4px 2px;")
        sr.addWidget(self.st, 1)
        left.addLayout(sr, 4, 1)
        
        left.addWidget(self._lbl("结束时间：", lbl_sty), 5, 0)
        er = QHBoxLayout(); er.setSpacing(6)
        self.ed = QDateEdit(); self.ed.setCalendarPopup(True); self.ed.setDate(QDate.currentDate())
        self.ed.setDisplayFormat("MM-dd")
        self.ed.setStyleSheet("font-size:22px; padding:4px 2px;")
        er.addWidget(self.ed, 3)
        self.et = QTimeEdit(); self.et.setTime(QTime.currentTime().addSecs(3600)); self.et.setDisplayFormat("HH:mm"); self.et.setStyleSheet("font-size:22px; padding:4px 2px;")
        er.addWidget(self.et, 1)
        left.addLayout(er, 5, 1)
        
        body.addLayout(left, 2)
        
        right = QVBoxLayout(); right.setSpacing(8)
        right.addWidget(self._lbl("备注：", lbl_sty))
        self.note = QPlainTextEdit(); self.note.setPlaceholderText("输入备注信息..."); self.note.setStyleSheet("font-size:26px;"); right.addWidget(self.note, 1)
        body.addLayout(right, 3)
        l.addLayout(body)
        
        bh = QHBoxLayout(); bh.setSpacing(10)
        self.cb = QCheckBox("同步到意向客户")
        self.cb.setStyleSheet("QCheckBox { color:#07c160; font-size:24px; font-weight:600; spacing:6px; border:none; background:transparent; } QCheckBox::indicator { width:16px; height:16px; }")
        bh.addWidget(self.cb); bh.addStretch()
        
        self.sv = QPushButton("保存")
        self.sv.setStyleSheet("QPushButton { background:#07c160; color:#fff; padding:8px 22px; border-radius:5px; border:none; font-size:24px; font-weight:600; } QPushButton:hover { background:#06ad56; }")
        self.sv.clicked.connect(self.save)
        self.cl = QPushButton("清空")
        self.cl.setStyleSheet("QPushButton { background: transparent; color:#5a5a7a; padding:8px 22px; border-radius:5px; border:1px solid #d1d5db; font-size:24px; } QPushButton:hover { background:#f0f0f5; }")
        self.cl.clicked.connect(self.clear)
        bh.addWidget(self.sv); bh.addWidget(self.cl)
        l.addLayout(bh)
        outer.addWidget(card)

    def _lbl(self, text, style):
        lbl = QLabel(text); lbl.setStyleSheet(style); return lbl

    def _filter_phone(self):
        txt = self.phone.text()
        filtered = ''.join(ch for ch in txt if ch.isdigit())
        if filtered != txt:
            self.phone.blockSignals(True)
            self.phone.setText(filtered)
            self.phone.blockSignals(False)

    def load(self, tid):
        self.tid = tid
        self.form_title.setText("编辑任务 #" + str(tid))
        t = self.db.get_task_by_id(tid)
        if not t: return
        self.name.setText(str(t[1] or ""))
        self.phone.setText(str(t[2] or ""))
        s_val = str(t[3] or ""); idx_s = self.sub.findText(s_val); self.sub.setCurrentIndex(idx_s if idx_s >= 0 else 0)
        i_val = str(t[4] or ""); idx_i = self.inq.findText(i_val); self.inq.setCurrentIndex(idx_i if idx_i >= 0 else 0)
        if t[6]:
            try:
                sdt = datetime.strptime(str(t[6])[:19], "%Y-%m-%d %H:%M:%S" if len(str(t[6]))>16 else "%Y-%m-%d %H:%M")
                self.sd.setDate(QDate(sdt.year, sdt.month, sdt.day)); self.st.setTime(QTime(sdt.hour, sdt.minute))
            except: pass
        if t[7]:
            try:
                edt = datetime.strptime(str(t[7])[:19], "%Y-%m-%d %H:%M:%S" if len(str(t[7]))>16 else "%Y-%m-%d %H:%M")
                self.ed.setDate(QDate(edt.year, edt.month, edt.day)); self.et.setTime(QTime(edt.hour, edt.minute))
            except: pass
        self.note.setPlainText(str(t[5] or "")); self.cb.setChecked(False)

    def clear(self):
        self.tid = None; self.form_title.setText("新建任务")
        self.name.clear(); self.phone.clear()
        self.sub.setCurrentIndex(0); self.inq.setCurrentIndex(0)
        self.sd.setDate(QDate.currentDate()); self.st.setTime(QTime.currentTime())
        self.ed.setDate(QDate.currentDate()); self.et.setTime(QTime.currentTime().addSecs(3600))
        self.note.clear(); self.cb.setChecked(False)

    def check_time_conflict(self, st, et, exclude_tid=None):
        """检查时间是否与已有任务冲突"""
        try:
            new_start = datetime.strptime(st, "%Y-%m-%d %H:%M")
            new_end = datetime.strptime(et, "%Y-%m-%d %H:%M")
            
            # 获取所有未删除的任务
            tasks = self.db.get_tasks("current")
            conflicts = []
            
            for t in tasks:
                tid = t[0]
                # 如果是编辑模式，排除当前任务
                if exclude_tid and tid == exclude_tid:
                    continue
                
                task_start_str = t[6]
                task_end_str = t[7]
                
                if not task_start_str or not task_end_str:
                    continue
                
                try:
                    task_start = datetime.strptime(str(task_start_str).replace("/","-")[:19], 
                                                  "%Y-%m-%d %H:%M:%S" if len(str(task_start_str)) > 16 else "%Y-%m-%d %H:%M")
                    task_end = datetime.strptime(str(task_end_str).replace("/","-")[:19], 
                                                "%Y-%m-%d %H:%M:%S" if len(str(task_end_str)) > 16 else "%Y-%m-%d %H:%M")
                    
                    # 检查时间是否重叠：新任务的开始时间在已有任务的时间范围内，或新任务的结束时间在已有任务的时间范围内
                    if (new_start < task_end and new_end > task_start):
                        conflicts.append({
                            'id': tid,
                            'name': t[1] or '未知',
                            'start': task_start.strftime("%m-%d %H:%M"),
                            'end': task_end.strftime("%m-%d %H:%M")
                        })
                except:
                    continue
            
            return conflicts
        except:
            return []

    def save(self):
        n = self.name.text().strip(); p = self.phone.text().strip()
        if not n or not p: QMessageBox.warning(self, "提示", "姓名和电话不能为空"); return
        s = self.sub.currentText().strip(); cat = "首咨" if s == "首咨" else "库存"
        i = self.inq.currentText()
        st = self.sd.date().toString("yyyy-MM-dd") + " " + self.st.time().toString("HH:mm")
        et = self.ed.date().toString("yyyy-MM-dd") + " " + self.et.time().toString("HH:mm")
        note = self.note.toPlainText().strip()
        
        # 检查时间冲突
        conflicts = self.check_time_conflict(st, et, self.tid)
        if conflicts:
            conflict_msg = "检测到时间冲突的任务：\n\n"
            for idx, c in enumerate(conflicts, 1):
                conflict_msg += f"{idx}. {c['name']} ({c['start']} - {c['end']})\n"
            conflict_msg += "\n是否继续保存？"
            
            reply = QMessageBox.question(self, "时间冲突提醒", conflict_msg, 
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        if self.tid: self.db.update_task(self.tid, n, p, s, i, note, st, et, cat)
        else: self.tid = self.db.add_task(n, p, s, i, note, st, et, cat); self.form_title.setText("编辑任务 #" + str(self.tid))
        if self.cb.isChecked(): self.db.add_intention(n, p, s, note, "任务同步")
        self.saved.emit()
        QMessageBox.information(self, "成功", "保存成功")


class MW(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("光照超级备忘录")
        screen = QDesktopWidget().availableGeometry()
        w, h = max(1200, int(screen.width() * 0.78)), max(800, int(screen.height() * 0.78))
        x, y = (screen.width() - w) // 2, (screen.height() - h) // 2
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(900, 600)
        
        self.db = DB()
        self.tm = TaskModel(); self.em = TaskModel(); self.rm = TaskModel(ac=True); self.im = IntModel()
        self.active = "current"; self._cat_filter = None
        self.ad = set(); self.lc = ""; self.last_tid = None
        
        self._setup_ui(); self._switch_view("current")
        self.timer = QTimer(self); self.timer.timeout.connect(self._check); self.timer.start(8000)

    def _setup_ui(self):
        cw = QWidget()
        ml = QHBoxLayout(cw); ml.setSpacing(0); ml.setContentsMargins(0, 0, 0, 0)
        
        sp = QWidget(); sp.setFixedWidth(460); sp.setStyleSheet("background: #07c160;")
        sl = QVBoxLayout(sp); sl.setSpacing(3); sl.setContentsMargins(0, 16, 0, 12)
        
        title = QLabel("  光照超级备忘录")
        title.setStyleSheet("color:#fff; font-size:29px; font-weight:bold; padding:6px 16px 12px 16px;")
        sl.addWidget(title)
        
        SBB = """QPushButton { text-align:left; padding:12px 20px; background:transparent; color:rgba(255,255,255,0.85); border:none; border-radius:6px; font-size:28px; margin:1px 10px; } QPushButton:hover { background:rgba(255,255,255,0.12); color:#fff; } QPushButton[active="true"] { background:rgba(255,255,255,0.20); color:#fff; font-weight:bold; }"""
        self.bt = {}
        nav = [("current","📋 当前任务"),("intention","⭐ 意向客户"),("expired","📅 已过期"),("recycle","🗑 回收站")]
        for k, text in nav:
            btn = QPushButton("  " + text)
            btn.setStyleSheet(SBB)
            btn.clicked.connect(lambda _, k2=k: self._switch_view(k2))
            sl.addWidget(btn); self.bt[k] = btn
        
        sl.addSpacing(8)
        stats_title = QLabel("  📊 统计信息")
        stats_title.setStyleSheet("color:rgba(255,255,255,0.95); font-size:26px; font-weight:bold; padding:6px 16px 4px 16px;")
        sl.addWidget(stats_title)
        self.stats_total = QLabel("  总任务：--")
        self.stats_total.setStyleSheet("color:rgba(255,255,255,0.85); font-size:24px; padding:2px 16px;")
        sl.addWidget(self.stats_total)
        self.stats_today = QLabel("  今日任务：--")
        self.stats_today.setStyleSheet("color:rgba(255,255,255,0.85); font-size:24px; padding:2px 16px;")
        sl.addWidget(self.stats_today)
        self.stats_sz = QLabel("  首咨任务：--")
        self.stats_sz.setStyleSheet("color:rgba(255,255,255,0.85); font-size:24px; padding:2px 16px;")
        sl.addWidget(self.stats_sz)
        self.stats_kc = QLabel("  库存任务：--")
        self.stats_kc.setStyleSheet("color:rgba(255,255,255,0.85); font-size:24px; padding:2px 16px;")
        sl.addWidget(self.stats_kc)
        self.stats_urgent = QLabel("  紧急：--")
        self.stats_urgent.setStyleSheet("color:rgba(255,255,255,0.85); font-size:24px; padding:2px 16px;")
        sl.addWidget(self.stats_urgent)
        sl.addSpacing(12)
        
        calc_hdr = QLabel("  人性化计算器")
        calc_hdr.setStyleSheet("color:rgba(255,255,255,0.80); font-size:26px; font-weight:bold; padding:4px 16px 6px 16px;")
        sl.addWidget(calc_hdr)
        
        self.calc = QPlainTextEdit(); self.calc.setMinimumHeight(300)
        self.calc.setPlaceholderText("输入算式... Enter/=双+")
        self.calc.setStyleSheet("background:rgba(255,255,255,0.18); color:rgba(255,255,255,0.95); border:1px solid rgba(255,255,255,0.25); border-radius:8px; padding:8px; font-size:26px; margin:0 8px;")
        self.calc.installEventFilter(self); sl.addWidget(self.calc)

        lbl_ver = QLabel("V6.83       作者：金闪闪")
        lbl_ver.setStyleSheet("color:rgba(255,255,255,0.7); font-size:22px; padding:4px 10px;")
        sl.addWidget(lbl_ver); sl.addSpacing(4)
        ml.addWidget(sp)
        
        mp = QWidget(); mp.setStyleSheet("background: #f5f6f8;")
        rl = QVBoxLayout(mp); rl.setSpacing(10); rl.setContentsMargins(16, 14, 16, 14)
        
        tb = QHBoxLayout()
        self.stl = QLabel("当前任务")
        self.stl.setStyleSheet("font-size:29px; font-weight:bold; color:#1a1a2e;")
        tb.addWidget(self.stl); tb.addSpacing(12)
        
        self.btn_cat_all = QPushButton("全部"); self.btn_cat_all.setCheckable(True); self.btn_cat_all.setChecked(True)
        self.btn_cat_all.setStyleSheet("""QPushButton { padding:5px 14px; border-radius:4px; border:1px solid #d1d5db; font-size:26px; font-weight:600; background:#07c160; color:#fff; border-color:#07c160; }""")
        self.btn_cat_all.clicked.connect(lambda: self._set_cat(None))
        self.btn_cat_sz = QPushButton("首咨"); self.btn_cat_sz.setCheckable(True)
        self.btn_cat_sz.setStyleSheet("""QPushButton { padding:5px 14px; border-radius:4px; border:1px solid #d1d5db; font-size:26px; font-weight:600; background:white; color:#5a5a7a; } QPushButton:hover { background:#e8f5e9; }""")
        self.btn_cat_sz.clicked.connect(lambda: self._set_cat("首咨"))
        self.btn_cat_kc = QPushButton("库存"); self.btn_cat_kc.setCheckable(True)
        self.btn_cat_kc.setStyleSheet("""QPushButton { padding:5px 14px; border-radius:4px; border:1px solid #d1d5db; font-size:26px; font-weight:600; background:white; color:#5a5a7a; } QPushButton:hover { background:#e8f5e9; }""")
        self.btn_cat_kc.clicked.connect(lambda: self._set_cat("库存"))
        tb.addWidget(self.btn_cat_all); tb.addWidget(self.btn_cat_sz); tb.addWidget(self.btn_cat_kc)
        tb.addStretch()
        
        tb.addWidget(QLabel("搜索："))
        self.sr = QLineEdit(); self.sr.setMaximumWidth(200)
        self.sr.setPlaceholderText("姓名/电话/科目...")
        self.sr.setStyleSheet("padding:7px 12px; border:1px solid #d1d5db; border-radius:5px; background:white; color:#1a1a2e; font-size:24px;")
        self.sr.textChanged.connect(lambda: self._load_view(self.active, self.sr.text().strip()))
        tb.addWidget(self.sr)
                # 导入导出按钮
        self.btn_imp = QPushButton("导入")
        self.btn_imp.setStyleSheet("QPushButton { background:transparent; color:#1976d2; padding:7px 16px; border-radius:5px; border:1px solid #1976d2; font-size:24px; font-weight:600; } QPushButton:hover { background:rgba(25,118,210,0.08); }")
        self.btn_imp.clicked.connect(self._import_csv)
        tb.addWidget(self.btn_imp)
        self.btn_exp = QPushButton("导出")
        self.btn_exp.setStyleSheet("QPushButton { background:transparent; color:#1976d2; padding:7px 16px; border-radius:5px; border:1px solid #1976d2; font-size:24px; font-weight:600; } QPushButton:hover { background:rgba(25,118,210,0.08); }")
        self.btn_exp.clicked.connect(self._export_csv)
        tb.addWidget(self.btn_exp)
        rl.addLayout(tb)
        
        self.tb = QTableView(); self.tb.setAlternatingRowColors(True)
        self.tb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb.clicked.connect(self._click)
        self.tb.horizontalHeader().setSectionsClickable(True)
        self.tb.horizontalHeader().sectionClicked.connect(lambda c: self.tb.model().sort(c, Qt.AscendingOrder) if hasattr(self.tb.model(),"sort") else None)
        self.tb.verticalHeader().setDefaultSectionSize(46)
        self.tb.setShowGrid(False)
        self.tb.setStyleSheet("""QTableView { background:white; border:1px solid #e0e0e0; border-radius:6px; gridline-color:#f0f0f5; color:#333; font-size:24px; } QTableView::item { padding:6px 10px; } QTableView::item:alternate { background:#fafafc; } QTableView::item:selected { background:#07c160; color:#fff; } QTableView::item:hover { background:#e8f5e9; color:#333; } QHeaderView::section { background:#fafafc; color:#666; padding:8px 10px; border:none; border-bottom:1px solid #e0e0e0; font-size:24px; font-weight:600; }""")
        self.tb.setStyleSheet("""
            QTableView {
                border: 1px solid #e0e0e0;
                background: #ffffff;
                alternate-background-color: #f8f9fa;
                gridline-color: #e0e0e0;
            }
            QTableView::item {
                border: none;
            }
            QTableView::item:selected {
                background: #1976d2;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #f5f5f5;
                border: 1px solid #e0e0e0;
                padding: 4px;
            }
        """)
        rl.addWidget(self.tb, 2)

        
        bb = QHBoxLayout(); bb.setSpacing(8)
        self.btn_sel = QPushButton("全选")
        self.btn_sel.setStyleSheet("QPushButton { background:transparent; color:#576b95; padding:7px 16px; border-radius:5px; border:1px solid #576b95; font-size:24px; font-weight:600; } QPushButton:hover { background:rgba(87,107,149,0.08); }")
        self.btn_sel.clicked.connect(self._sel_all); bb.addWidget(self.btn_sel)
        
        self.btn_del = QPushButton("删除")
        self.btn_del.setStyleSheet("QPushButton { background:transparent; color:#fa5151; padding:7px 16px; border-radius:5px; border:1px solid #fa5151; font-size:24px; font-weight:600; } QPushButton:hover { background:rgba(250,81,81,0.08); }")
        self.btn_del.clicked.connect(self._batch); bb.addWidget(self.btn_del)
        
        self.btn_res = QPushButton("恢复")
        self.btn_res.setStyleSheet("QPushButton { background:transparent; color:#07c160; padding:7px 16px; border-radius:5px; border:1px solid #07c160; font-size:24px; font-weight:600; } QPushButton:hover { background:rgba(7,193,96,0.08); }")
        self.btn_res.clicked.connect(self._batch); self.btn_res.hide(); bb.addWidget(self.btn_res)
        
        self.btn_int = QPushButton("+ 新建意向客户")
        self.btn_int.setStyleSheet("QPushButton { background:transparent; color:#07c160; padding:7px 16px; border-radius:5px; border:1px solid #07c160; font-size:24px; font-weight:600; } QPushButton:hover { background:rgba(7,193,96,0.08); }")
        self.btn_int.clicked.connect(self._add_int); self.btn_int.hide(); bb.addWidget(self.btn_int)
        bb.addStretch()
        
        self.btn_new = QPushButton("+ 新建任务")
        self.btn_new.setStyleSheet("QPushButton { background:#07c160; color:#fff; padding:9px 22px; border-radius:6px; border:none; font-size:26px; font-weight:600; } QPushButton:hover { background:#06ad56; }")
        self.btn_new.clicked.connect(lambda: self.form.clear()); bb.addWidget(self.btn_new)
        rl.addLayout(bb)
        
        self.form = TaskForm(self.db, parent=self)
        self.form.saved.connect(lambda: self._load_view(self.active, self.sr.text().strip()))
        rl.addWidget(self.form)
        ml.addWidget(mp, 1); self.setCentralWidget(cw)

    def _cat_btn_style(self, active):
        return """QPushButton { padding:5px 14px; border-radius:4px; border:1px solid #d1d5db; font-size:26px; font-weight:600; background:#07c160; color:#fff; border-color:#07c160; }""" if active else """QPushButton { padding:5px 14px; border-radius:4px; border:1px solid #d1d5db; font-size:26px; font-weight:600; background:white; color:#5a5a7a; } QPushButton:hover { background:#e8f5e9; }"""

    def _set_cat(self, cat):
        self._cat_filter = cat
        self.btn_cat_all.setStyleSheet(self._cat_btn_style(cat is None))
        self.btn_cat_sz.setStyleSheet(self._cat_btn_style(cat == "首咨"))
        self.btn_cat_kc.setStyleSheet(self._cat_btn_style(cat == "库存"))
        self._load_view(self.active, self.sr.text().strip())

    def _switch_view(self, s):
        self.active = s
        nav = {"current":"当前任务","intention":"意向客户","expired":"已过期","recycle":"回收站"}
        self.stl.setText(nav.get(s, ""))
        is_cur = (s == "current")
        self.btn_cat_all.setVisible(is_cur); self.btn_cat_sz.setVisible(is_cur); self.btn_cat_kc.setVisible(is_cur)
        is_int = (s == "intention"); is_rec = (s == "recycle")
        self.btn_del.setText("彻底删除" if is_rec else "删除")
        self.btn_res.setVisible(is_rec); self.btn_res.hide()
        self.btn_int.setVisible(is_int)
        self.btn_new.setText("+ 新建任务" if not is_int else "+ 新建意向客户")
        for k, v in self.bt.items():
            v.setProperty("active", k == s); v.style().unpolish(v); v.style().polish(v)
        self._load_view(s, self.sr.text().strip())

    def _load_view(self, s, q=""):
        self.form.clear()
        if s == "intention":
            d = self.db.get_intentions(deleted=False, s=q); self.im._d = d; self.im.layoutChanged.emit(); self.tb.setModel(self.im)
        else:
            m = {"expired":self.em,"recycle":self.rm}.get(s, self.tm)
            cat = self._cat_filter if s == "current" else None
            d = self.db.get_tasks(s, q, cat); m._d = d; m.layoutChanged.emit(); self.tb.setModel(m)
        self._resize_cols(); self._upd_btns(); self._update_stats()

    def _resize_cols(self):
        h = self.tb.horizontalHeader()
        if not h: return
        try:
            m = hasattr(h, "setSectionResizeMode")
            if m:
                h.setSectionResizeMode(0, QHeaderView.Fixed); h.resizeSection(0, 62)
                h.setSectionResizeMode(1, QHeaderView.Fixed); h.resizeSection(1, 44)
            else:
                h.setResizeMode(0, QHeaderView.Fixed); h.resizeSection(0, 62)
                h.setResizeMode(1, QHeaderView.Fixed); h.resizeSection(1, 44)
            n = self.tb.model().columnCount()
            for i in range(2, n):
                if m: h.setSectionResizeMode(i, QHeaderView.Stretch)
                else: h.setResizeMode(i, QHeaderView.Stretch)
        except: pass

    def _click(self, i):
        if not i.isValid(): return
        m = self.tb.model()
        if isinstance(m, IntModel):
            r = i.row()
            if i.column() == 1 and hasattr(m, '_c'):
                if r in m._c: m._c.discard(r)
                else: m._c.add(r)
                m.dataChanged.emit(i, i); self.tb.viewport().update(); self._upd_btns()
            if r < len(m._d):
                t = m._d[r]
                QMessageBox.information(self, "意向客户详情",
                    "姓名："+str(t[1])+"\n电话："+str(t[2])+"\n科目："+str(t[3] or "-")+"\n备注："+str(t[4] or "-")+"\n来源："+str(t[5] or "-"))
            return
        if i.column() == 1 and hasattr(m, '_c'):
            r = i.row()
            if r in m._c: m._c.discard(r)
            else: m._c.add(r)
            m.dataChanged.emit(i, i); self.tb.viewport().update(); self._upd_btns()
        r = i.row()
        if r < len(m._d):
            try: self.form.load(m._d[r][0])
            except: self.form.clear()

    def _upd_btns(self):
        m = self.tb.model()
        if not hasattr(m, '_c'): return
        c = len(m._c)
        if self.active == "recycle":
            self.btn_res.setVisible(c > 0)

    def _update_stats(self):
        d = self.db
        total = d.count_tasks()
        today = d.count_today_tasks()
        sz = d.count_current_tasks(cat="首咨")
        kc = d.count_current_tasks(cat="库存")
        urgent = d.count_today_urgent()
        self.stats_total.setText(f"  总任务：{total}")
        self.stats_today.setText(f"  今日任务：{today}")
        self.stats_sz.setText(f"  首咨任务：{sz}")
        self.stats_kc.setText(f"  库存任务：{kc}")
        self.stats_urgent.setText(f"  紧急：{urgent}")

    def _sel_all(self):
        m = self.tb.model()
        if not hasattr(m, '_c'): return
        if len(m._c) == m.rowCount(): m._c.clear()
        else: m._c = set(range(m.rowCount()))
        m.dataChanged.emit(m.createIndex(0, 0), m.createIndex(m.rowCount()-1, 0))
        self.tb.viewport().update(); self._upd_btns()

    def _batch(self):
        m = self.tb.model(); ids = m.checked()
        if not ids: QMessageBox.warning(self, "提示", "请勾选记录"); return
        is_int = isinstance(m, IntModel)
        if is_int:
            if self.active == "recycle":
                if QMessageBox.Yes != QMessageBox.question(self,"确认","确定彻底删除"+str(len(ids))+"条？"): return
                for u in ids: self.db.delete_intention(u); QApplication.processEvents()
            elif self.btn_del.text() == "恢复":
                if QMessageBox.Yes != QMessageBox.question(self,"确认","确定恢复"+str(len(ids))+"条？"): return
                self.db.batch_restore_intention(ids)
            else:
                if QMessageBox.Yes != QMessageBox.question(self,"确认","确定删除"+str(len(ids))+"条？"): return
                self.db.batch_delete_intention(ids)
        else:
            if self.active == "recycle":
                if self.btn_del.text() == "恢复":
                    if QMessageBox.Yes != QMessageBox.question(self,"确认","确定恢复"+str(len(ids))+"条？"): return
                    self.db.batch_restore(ids)
                else:
                    if QMessageBox.Yes != QMessageBox.question(self,"确认","确定彻底删除"+str(len(ids))+"条？"): return
                    for tid in ids: self.db.delete_task(tid, False); QApplication.processEvents()
            else:
                if QMessageBox.Yes != QMessageBox.question(self,"确认","确定删除"+str(len(ids))+"条？"): return
                self.db.batch_delete(ids)
        m.clear_chk(); self._load_view(self.active, self.sr.text().strip())

    def _add_int(self):
        dlg = QDialog(self); dlg.setWindowTitle("新建意向客户"); dlg.setMinimumWidth(380)
        dlg.setStyleSheet("QDialog { background:white; } QLabel { font-size:24px; color:#5a5a7a; }")
        l = QVBoxLayout(dlg); l.setSpacing(12); l.setContentsMargins(18, 18, 18, 18)
        g = QGridLayout(); g.setSpacing(8)
        inp = "padding:7px 10px; border:1px solid #d1d5db; border-radius:5px; font-size:24px;"
        g.addWidget(QLabel("姓名："),0,0); na=QLineEdit(); na.setStyleSheet(inp); g.addWidget(na,0,1)
        g.addWidget(QLabel("电话："),1,0); ph=QLineEdit(); ph.setStyleSheet(inp); g.addWidget(ph,1,1)
        g.addWidget(QLabel("科目："),2,0); sj=QLineEdit(); sj.setStyleSheet(inp); g.addWidget(sj,2,1)
        g.addWidget(QLabel("备注："),3,0); nt=QPlainTextEdit(); nt.setMaximumHeight(60); nt.setStyleSheet(inp); g.addWidget(nt,3,1)
        l.addLayout(g)
        bh = QHBoxLayout(); bh.addStretch()
        ok = QPushButton("保存"); ok.setStyleSheet("QPushButton { background:#07c160; color:#fff; padding:8px 24px; border-radius:5px; font-size:24px; font-weight:600; } QPushButton:hover { background:#06ad56; }")
        cancel = QPushButton("取消"); cancel.setStyleSheet("QPushButton { background:transparent; color:#5a5a7a; padding:8px 24px; border-radius:5px; border:1px solid #d1d5db; font-size:24px; }")
        bh.addWidget(cancel); bh.addWidget(ok); l.addLayout(bh)
        def do_save():
            n = na.text().strip()
            if not n: QMessageBox.warning(dlg,"提示","姓名不能为空"); return
            self.db.add_intention(n, ph.text().strip(), sj.text().strip(), nt.toPlainText().strip(), "手动创建")
            dlg.accept(); self._load_view(self.active, self.sr.text().strip())
        ok.clicked.connect(do_save); cancel.clicked.connect(dlg.reject); dlg.exec()

    def _check(self):
        try:
            now = datetime.now()
            tasks = self.db.get_tasks("current")
            for t in tasks:
                tid = t[0]
                if tid in self.ad: continue
                st = t[6]
                if not st: continue
                et = t[7]
                if et:
                    try:
                        et_s = str(et).replace("/","-")
                        et_dt = datetime.strptime(et_s[:19], "%Y-%m-%d %H:%M:%S" if len(et_s)>16 else "%Y-%m-%d %H:%M")
                        if et_dt <= now: continue
                    except: pass
                rm = t[8]
                if rm:
                    rm_str = str(rm).replace("/","-")
                    rt = datetime.strptime(rm_str[:19], "%Y-%m-%d %H:%M:%S" if len(rm_str)>16 else "%Y-%m-%d %H:%M")
                else:
                    st = t[6]
                    st_str = str(st).replace("/","-")
                    stp = datetime.strptime(st_str[:19], "%Y-%m-%d %H:%M:%S" if len(st_str)>16 else "%Y-%m-%d %H:%M")
                    rt = stp - timedelta(minutes=5)
                if rt <= now:
                    self.ad.add(tid)
                    dlg = ReminderDlg(t, self)
                    res = dlg.exec()
                    if res == QDialog.Accepted:
                        new_rm = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M")
                    else:
                        new_rm = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
                    self.db.c.execute("UPDATE tasks SET remind_time=? WHERE id=?", (new_rm, tid))
                    self.db.conn.commit()
                    self.ad.discard(tid)
        except: pass

    def eventFilter(self, obj, event):
        if obj != self.calc or event.type() != QEvent.KeyPress: return False
        k = event.text()
        is_enter = event.key() in (Qt.Key_Return, Qt.Key_Enter)
        if is_enter or k == "=":
            self._eval(True if is_enter else False)
            return True if is_enter else False
        if k == "+":
            if self.lc == "+": self._eval(True); self.lc = ""; return True
            self.lc = k; return False
        self.lc = k; return False

    def _eval(self, full_line=False):
        c = self.calc.textCursor(); c.select(QTextCursor.LineUnderCursor)
        line = c.selectedText().strip().rstrip("+").rstrip("=")
        if not line: return
        if not any(op in line for op in ["+","-","*","/"]):
            if full_line:
                c.movePosition(QTextCursor.EndOfLine); c.insertText("\n")
            return
        try:
            ex = line.replace("^","**").replace("×","*").replace("÷","/")
            safe = set("0123456789+-*/().% ")
            if not all(ch in safe or ch.isspace() for ch in ex): return
            res = eval(ex, {"__builtins__":{}}, {})
            if isinstance(res, float) and res == int(res): res = int(res)
            c.removeSelectedText(); c.insertText(line + " = " + str(res))
            c.movePosition(QTextCursor.EndOfLine); c.insertText("\n" + str(res))
            self.lc = ""
        except: pass

    def closeEvent(self, e):
        if QMessageBox.Yes == QMessageBox.question(self,"确认退出","确定要退出光照超级备忘录吗？", QMessageBox.Yes|QMessageBox.No, QMessageBox.No):
            self.timer.stop(); self.db.conn.close(); e.accept()
        else: e.ignore()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出任务数据", "", "CSV文件 (*.csv);;所有文件 (*)")
        if not path:
            return
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.db.c.execute("SELECT * FROM tasks")
            tasks = self.db.c.fetchall()
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["序号", "客户姓名", "电话", "意向度", "开始时间", "结束时间", "任务类型", "状态", "备注"])
                for i, t in enumerate(tasks):
                    name = t[1] if t[1] else ""
                    phone = t[2] if t[2] else ""
                    intention = t[4] if t[4] else ""
                    start_time = t[6] if t[6] else ""
                    end_time = t[7] if t[7] else ""
                    category = t[12] if t[12] else "库存"
                    note = t[5] if t[5] else ""
                    if t[9] == 1:
                        status = "回收站"
                    elif end_time and end_time <= now:
                        status = "已过期"
                    else:
                        status = "当前任务"
                    writer.writerow([i+1, name, phone, intention, start_time, end_time, category, status, note])
            QMessageBox.information(self, "成功", f"已导出 {len(tasks)} 条任务")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    def _fix_time(self, t):
        if not t: return t
        t = t.strip().replace("/","-")
        if " " not in t: t += " 00:00"
        parts = t.split(" ")
        dp = parts[0].split("-")
        parts[0] = f"{int(dp[0]):04d}-{int(dp[1]):02d}-{int(dp[2]):02d}"
        time_part = parts[1].split(":")[0:2]
        parts[1] = f"{int(time_part[0]):02d}:{int(time_part[1]):02d}"
        return " ".join(parts)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入任务数据", "", "CSV文件 (*.csv);;所有文件 (*)")
        if not path: return
        count = 0; bad = 0
        try:
            content = open(path, 'r', encoding='utf-8-sig').read()
        except:
            try:
                content = open(path, 'r', encoding='gbk').read()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法读取文件:\n{str(e)}")
                return
        lines = content.strip().split('\n')
        if len(lines) < 2:
            QMessageBox.information(self, "提示", "文件中没有数据行")
            return
        for i, line in enumerate(lines):
            if i == 0: continue
            parts = [c.strip() for c in line.split(',')]
            if len(parts) < 6: bad += 1; continue
            name = parts[1]
            start_time = parts[4]
            if not name or not start_time: bad += 1; continue
            try:
                st = start_time.replace("/","-").replace("：",":")
                if " " not in st: st += " 00:00"
                st = st[:16]
                et = parts[5] if len(parts) > 5 else ""
                if et:
                    et = et.replace("/","-").replace("：",":")
                    if " " not in et: et += " 23:59"
                    et = et[:16]
                else: et = st
                phone = parts[2] if len(parts) > 2 else ""
                intention = parts[3] if len(parts) > 3 else "高意向"
                category = parts[6] if len(parts) > 6 else "库存"
                remark = parts[8] if len(parts) > 8 else ""
                rt = (datetime.strptime(st,"%Y-%m-%d %H:%M") - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
                self.db.c.execute("INSERT INTO tasks(name,phone,subject,intention,note,start_time,end_time,remind_time,category) VALUES(?,?,?,?,?,?,?,?,?)", (name, phone, category, intention, remark, st, et, rt, category))
                self.db.conn.commit(); count += 1
            except Exception as e:
                bad += 1
        self._load_view(self.active, self.sr.text().strip())
        msg = f"已导入 {count} 条任务"
        if bad > 0: msg += f"\n跳过 {bad} 条"
        QMessageBox.information(self, "导入完成", msg)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 14)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(CAL_POPUP_STYLE)
    w = MW(); w.show()
    sys.excepthook = lambda t, v, tb: QMessageBox.critical(None, "错误", f"程序异常:\n{str(v)}")
    sys.exit(app.exec_())