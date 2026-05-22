"""
SQLite数据库操作模块
使用Python内置sqlite3，无需额外安装数据库服务
"""

import sqlite3
import os
import logging
from datetime import datetime
from config.config import DATABASE_CONFIG

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器，负责所有数据表的创建和操作"""

    def __init__(self, db_path=None):
        """
        初始化数据库连接
        :param db_path: 数据库文件路径，默认使用配置文件中的路径
        """
        if db_path is None:
            db_path = DATABASE_CONFIG['db_path']

        # 确保数据库目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"创建数据库目录: {db_dir}")

        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _get_connection(self):
        """获取数据库连接"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            logger.info(f"数据库连接已建立: {self.db_path}")
        return self.conn

    def _init_database(self):
        """初始化数据库，创建所有必要的表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT UNIQUE NOT NULL,          -- 微信ID
                nickname TEXT,                       -- 昵称
                balance REAL DEFAULT 0.0,           -- 返利余额
                total_earnings REAL DEFAULT 0.0,    -- 累计收益
                total_orders INTEGER DEFAULT 0,     -- 累计订单数
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'        -- 用户状态: active/banned
            )
        ''')

        # 创建订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,      -- 订单号
                wxid TEXT NOT NULL,                 -- 用户微信ID
                platform TEXT NOT NULL,             -- 平台: taobao/jd/pdd/meituan
                product_title TEXT,                 -- 商品标题
                product_url TEXT,                   -- 商品链接
                original_price REAL,                -- 原价
                commission REAL DEFAULT 0.0,        -- 佣金总额
                user_rebate REAL DEFAULT 0.0,       -- 用户返利金额
                order_status TEXT DEFAULT 'pending',-- 订单状态: pending/paid/settled/failed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wxid) REFERENCES users(wxid)
            )
        ''')

        # 创建返利流水表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT NOT NULL,                 -- 用户微信ID
                type TEXT NOT NULL,                 -- 类型: rebate/withdraw/refund
                amount REAL NOT NULL,               -- 金额（正数为收入，负数为支出）
                balance_after REAL,                 -- 交易后余额
                description TEXT,                   -- 描述
                related_order_no TEXT,              -- 关联订单号
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wxid) REFERENCES users(wxid)
            )
        ''')

        # 创建提现记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT NOT NULL,                 -- 用户微信ID
                amount REAL NOT NULL,               -- 提现金额
                status TEXT DEFAULT 'pending',      -- 状态: pending/approved/rejected/completed
                payment_method TEXT,                -- 支付方式: wechat/alipay
                payment_account TEXT,               -- 支付账号
                remark TEXT,                        -- 备注
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,             -- 处理时间
                FOREIGN KEY (wxid) REFERENCES users(wxid)
            )
        ''')

        # 创建群聊消息统计表（用于防封控制）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_msg_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,             -- 群聊ID
                hour_key TEXT NOT NULL,             -- 小时标识: YYYY-MM-DD-HH
                msg_count INTEGER DEFAULT 0,        -- 消息数量
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, hour_key)
            )
        ''')

        # 创建签到记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT NOT NULL,                 -- 用户微信ID
                checkin_date DATE NOT NULL,         -- 签到日期: YYYY-MM-DD
                reward_amount REAL NOT NULL,        -- 奖励金额
                continuous_days INTEGER DEFAULT 1,  -- 连续签到天数
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(wxid, checkin_date),
                FOREIGN KEY (wxid) REFERENCES users(wxid)
            )
        ''')
        
        # [新] 创建用户偏好表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                wxid TEXT PRIMARY KEY,
                default_city TEXT DEFAULT '北京',
                favorite_categories TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # [新] 创建搜索历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT NOT NULL,
                keyword TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引以优化查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_wxid ON users(wxid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_wxid ON orders(wxid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_wxid ON transactions(wxid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawals_wxid ON withdrawals(wxid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_checkins_wxid ON checkins(wxid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_checkins_date ON checkins(checkin_date)')

        # 联盟订单同步游标
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_sync_state (
                platform TEXT PRIMARY KEY,
                last_sync_time TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # OpenClaw 模式：无法主动推送时暂存结算通知
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP
            )
        ''')

        self._migrate_orders_schema(cursor)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_platform_oid ON orders(platform, platform_order_id)')

        conn.commit()
        logger.info("数据库初始化完成")

    def _migrate_orders_schema(self, cursor):
        """为 orders 表增加联盟订单关联字段（兼容旧库）"""
        cursor.execute('PRAGMA table_info(orders)')
        existing = {row[1] for row in cursor.fetchall()}
        migrations = {
            'platform_order_id': 'TEXT',
            'platform_item_id': 'TEXT',
            'platform_status': 'TEXT',
            'notify_chat': 'TEXT',
            'notify_is_group': 'INTEGER DEFAULT 0',
            'user_nickname': 'TEXT',
            # bot_convert=用户经机器人私聊/群聊转链；空或其它=不可参与返利结算
            'rebate_source': 'TEXT',
        }
        for col, col_type in migrations.items():
            if col not in existing:
                cursor.execute(f'ALTER TABLE orders ADD COLUMN {col} {col_type}')
                logger.info('orders 表新增字段: %s', col)

    def execute_query(self, query, params=None, fetch=False, fetch_all=False):
        """
        执行SQL查询
        :param query: SQL语句
        :param params: 参数元组
        :param fetch: 是否返回单条结果
        :param fetch_all: 是否返回所有结果
        :return: 查询结果
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if fetch:
                result = cursor.fetchone()
                return result
            elif fetch_all:
                result = cursor.fetchall()
                return result
            else:
                conn.commit()
                return cursor.lastrowid

        except sqlite3.Error as e:
            logger.error(f"数据库查询错误: {e}, SQL: {query}")
            raise

    # ==================== 用户相关操作 ====================

    def add_user(self, wxid, nickname=None):
        """添加新用户"""
        try:
            self.execute_query(
                'INSERT OR IGNORE INTO users (wxid, nickname) VALUES (?, ?)',
                (wxid, nickname)
            )
            logger.info(f"用户已添加: {wxid}")
            return True
        except Exception as e:
            logger.error(f"添加用户失败: {e}")
            return False

    def get_user(self, wxid):
        """获取用户信息"""
        return self.execute_query(
            'SELECT * FROM users WHERE wxid = ?',
            (wxid,),
            fetch=True
        )

    def update_user_balance(self, wxid, amount):
        """更新用户余额"""
        try:
            # 先获取当前余额
            user = self.get_user(wxid)
            if not user:
                logger.error(f"用户不存在: {wxid}")
                return False

            old_balance = user['balance']
            new_balance = old_balance + amount

            self.execute_query(
                'UPDATE users SET balance = ?, total_earnings = total_earnings + ?, updated_at = CURRENT_TIMESTAMP WHERE wxid = ?',
                (new_balance, amount if amount > 0 else 0, wxid)
            )

            # 记录流水
            self.add_transaction(wxid, 'rebate' if amount > 0 else 'withdraw',
                               amount, new_balance, f"{'返利' if amount > 0 else '提现'} {abs(amount):.2f}元")

            logger.info(f"用户 {wxid} 余额更新: {old_balance:.2f} -> {new_balance:.2f}")
            return True
        except Exception as e:
            logger.error(f"更新用户余额失败: {e}")
            return False

    def increase_order_count(self, wxid):
        """增加用户订单计数"""
        self.execute_query(
            'UPDATE users SET total_orders = total_orders + 1, updated_at = CURRENT_TIMESTAMP WHERE wxid = ?',
            (wxid,)
        )

    # ==================== 订单相关操作 ====================

    def add_order(self, order_no, wxid, platform, product_title=None,
                  product_url=None, original_price=None, commission=0.0,
                  user_rebate=0.0, platform_order_id=None, platform_item_id=None,
                  platform_status=None, notify_chat=None, notify_is_group=0,
                  user_nickname=None, rebate_source='bot_convert'):
        """添加订单记录（仅 bot_convert 来源可在联盟同步时结算返利）"""
        try:
            self.execute_query(
                '''INSERT OR IGNORE INTO orders 
                   (order_no, wxid, platform, product_title, product_url, 
                    original_price, commission, user_rebate,
                    platform_order_id, platform_item_id, platform_status,
                    notify_chat, notify_is_group, user_nickname, rebate_source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (order_no, wxid, platform, product_title, product_url,
                 original_price, commission, user_rebate,
                 platform_order_id, platform_item_id, platform_status,
                 notify_chat, 1 if notify_is_group else 0, user_nickname,
                 rebate_source)
            )
            self.increase_order_count(wxid)
            logger.info(f"订单已添加: {order_no}")
            return True
        except Exception as e:
            logger.error(f"添加订单失败: {e}")
            return False

    def update_order_status(self, order_no, status):
        """更新订单状态"""
        self.execute_query(
            'UPDATE orders SET order_status = ?, updated_at = CURRENT_TIMESTAMP WHERE order_no = ?',
            (status, order_no)
        )

    def get_user_orders(self, wxid, limit=10):
        """获取用户订单列表"""
        return self.execute_query(
            'SELECT * FROM orders WHERE wxid = ? ORDER BY created_at DESC LIMIT ?',
            (wxid, limit),
            fetch_all=True
        )

    def get_pending_orders(self):
        """获取待处理的订单"""
        return self.execute_query(
            "SELECT * FROM orders WHERE order_status = 'pending'",
            fetch_all=True
        )

    def get_order_by_no(self, order_no):
        return self.execute_query(
            'SELECT * FROM orders WHERE order_no = ?',
            (order_no,),
            fetch=True,
        )

    def get_order_by_platform(self, platform, platform_order_id):
        if not platform_order_id:
            return None
        return self.execute_query(
            'SELECT * FROM orders WHERE platform = ? AND platform_order_id = ?',
            (platform, str(platform_order_id)),
            fetch=True,
        )

    def get_user_order_by_platform_order_id(self, wxid, platform_order_id, platform=None):
        """按用户 + 联盟/淘宝订单号查找内部订单"""
        pid = str(platform_order_id).strip()
        if not pid:
            return None
        if platform:
            return self.execute_query(
                '''SELECT * FROM orders WHERE wxid = ? AND platform = ?
                   AND platform_order_id = ? LIMIT 1''',
                (wxid, platform, pid),
                fetch=True,
            )
        return self.execute_query(
            '''SELECT * FROM orders WHERE wxid = ? AND platform_order_id = ?
               ORDER BY created_at DESC LIMIT 1''',
            (wxid, pid),
            fetch=True,
        )

    def link_platform_order(self, order_no, platform_order_id, platform_item_id=None,
                            platform_status=None, user_rebate=None):
        fields = ['platform_order_id = ?', 'updated_at = CURRENT_TIMESTAMP']
        params = [platform_order_id]
        if platform_item_id:
            fields.append('platform_item_id = ?')
            params.append(platform_item_id)
        if platform_status:
            fields.append('platform_status = ?')
            params.append(platform_status)
        if user_rebate is not None:
            fields.append('user_rebate = ?')
            params.append(user_rebate)
        params.append(order_no)
        self.execute_query(
            f"UPDATE orders SET {', '.join(fields)} WHERE order_no = ?",
            tuple(params),
        )

    def update_order_platform_status(self, order_no, platform_status):
        if platform_status is None:
            return
        self.execute_query(
            'UPDATE orders SET platform_status = ?, updated_at = CURRENT_TIMESTAMP WHERE order_no = ?',
            (platform_status, order_no),
        )

    def find_match_pending_order(self, wxid, platform, platform_item_id=None, within_days=15):
        """匹配待结算内部订单：须为机器人转链(bot_convert)，同用户+同平台+商品ID"""
        if platform_item_id:
            row = self.execute_query(
                '''SELECT * FROM orders WHERE wxid = ? AND platform = ?
                   AND rebate_source = 'bot_convert'
                   AND order_status IN ('pending', 'paid')
                   AND (platform_item_id = ? OR platform_item_id IS NULL OR platform_item_id = '')
                   AND datetime(created_at) >= datetime('now', ?)
                   ORDER BY CASE WHEN platform_item_id = ? THEN 0 ELSE 1 END, created_at DESC
                   LIMIT 1''',
                (wxid, platform, str(platform_item_id), f'-{within_days} days', str(platform_item_id)),
                fetch=True,
            )
            if row:
                return row
        return self.execute_query(
            '''SELECT * FROM orders WHERE wxid = ? AND platform = ?
               AND rebate_source = 'bot_convert'
               AND order_status IN ('pending', 'paid')
               AND platform_order_id IS NULL
               AND datetime(created_at) >= datetime('now', ?)
               ORDER BY created_at DESC LIMIT 1''',
            (wxid, platform, f'-{within_days} days'),
            fetch=True,
        )

    def is_order_rebate_eligible(self, order) -> bool:
        """是否允许结算推广奖励（仅机器人转链产生的记录）"""
        if not order:
            return False
        try:
            source = order['rebate_source']
        except (KeyError, TypeError):
            source = None
        return source == 'bot_convert'

    def get_order_sync_time(self, platform='all'):
        row = self.execute_query(
            'SELECT last_sync_time FROM order_sync_state WHERE platform = ?',
            (platform,),
            fetch=True,
        )
        return row['last_sync_time'] if row else None

    def set_order_sync_time(self, platform, sync_time):
        self.execute_query(
            '''INSERT INTO order_sync_state (platform, last_sync_time, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(platform) DO UPDATE SET
               last_sync_time = excluded.last_sync_time,
               updated_at = CURRENT_TIMESTAMP''',
            (platform, sync_time),
        )

    # ==================== 返利流水操作 ====================

    def add_transaction(self, wxid, trans_type, amount, balance_after, description=None,
                       related_order_no=None):
        """添加交易流水"""
        try:
            self.execute_query(
                '''INSERT INTO transactions (wxid, type, amount, balance_after, description, related_order_no)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (wxid, trans_type, amount, balance_after, description, related_order_no)
            )
            return True
        except Exception as e:
            logger.error(f"添加交易流水失败: {e}")
            return False

    def get_user_transactions(self, wxid, limit=20):
        """获取用户交易流水"""
        return self.execute_query(
            'SELECT * FROM transactions WHERE wxid = ? ORDER BY created_at DESC LIMIT ?',
            (wxid, limit),
            fetch_all=True
        )

    # ==================== 提现相关操作 ====================

    def add_withdrawal(self, wxid, amount, payment_method, payment_account, remark=None):
        """添加提现申请"""
        try:
            withdraw_id = self.execute_query(
                '''INSERT INTO withdrawals (wxid, amount, payment_method, payment_account, remark)
                   VALUES (?, ?, ?, ?, ?)''',
                (wxid, amount, payment_method, payment_account, remark)
            )
            logger.info(f"提现申请已提交: ID={withdraw_id}, 用户={wxid}, 金额={amount}")
            return withdraw_id
        except Exception as e:
            logger.error(f"添加提现申请失败: {e}")
            return None

    def update_withdrawal_status(self, withdraw_id, status):
        """更新提现状态"""
        self.execute_query(
            'UPDATE withdrawals SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?',
            (status, withdraw_id)
        )

    def get_user_withdrawals(self, wxid, limit=10):
        """获取用户提现记录"""
        return self.execute_query(
            'SELECT * FROM withdrawals WHERE wxid = ? ORDER BY created_at DESC LIMIT ?',
            (wxid, limit),
            fetch_all=True
        )

    def get_withdrawal(self, withdraw_id):
        """按 ID 获取提现记录"""
        return self.execute_query(
            'SELECT * FROM withdrawals WHERE id = ?',
            (withdraw_id,),
            fetch=True,
        )

    def get_user_pending_withdrawal(self, wxid):
        """获取用户待审核提现（仅一条）"""
        return self.execute_query(
            "SELECT * FROM withdrawals WHERE wxid = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (wxid,),
            fetch=True,
        )

    def get_pending_withdrawals(self, limit=20):
        """获取待审核提现列表"""
        return self.execute_query(
            "SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
            fetch_all=True,
        ) or []

    def apply_withdrawal(self, wxid, min_amount, payment_method='wechat', payment_account=''):
        """
        提交提现：冻结余额（扣减）并创建 pending 记录，等待管理员审核打款
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute('SELECT * FROM users WHERE wxid = ?', (wxid,))
            user = cursor.fetchone()
            if not user:
                conn.rollback()
                return {'success': False, 'message': '用户不存在'}

            balance = float(user['balance'])
            if balance < float(min_amount):
                conn.rollback()
                return {'success': False, 'message': f'余额不足 {min_amount:.0f} 元，无法提现'}

            cursor.execute(
                "SELECT id FROM withdrawals WHERE wxid = ? AND status = 'pending'",
                (wxid,),
            )
            if cursor.fetchone():
                conn.rollback()
                return {'success': False, 'message': '您已有待审核的提现申请，请等待管理员处理'}

            amount = balance
            new_balance = 0.0
            cursor.execute(
                'UPDATE users SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE wxid = ?',
                (new_balance, wxid),
            )
            cursor.execute(
                '''INSERT INTO withdrawals (wxid, amount, status, payment_method, payment_account, remark)
                   VALUES (?, ?, 'pending', ?, ?, ?)''',
                (wxid, amount, payment_method, payment_account, '用户申请提现'),
            )
            withdraw_id = cursor.lastrowid
            cursor.execute(
                '''INSERT INTO transactions (wxid, type, amount, balance_after, description)
                   VALUES (?, 'withdraw', ?, ?, ?)''',
                (wxid, -amount, new_balance, f'提现申请#{withdraw_id}（待审核）'),
            )
            conn.commit()
            logger.info('提现申请: id=%s wxid=%s amount=%.2f', withdraw_id, wxid, amount)
            return {'success': True, 'withdraw_id': withdraw_id, 'amount': amount}
        except Exception as e:
            conn.rollback()
            logger.error('提现申请失败: %s', e)
            return {'success': False, 'message': str(e)}

    def reject_withdrawal(self, withdraw_id, remark=None):
        """拒绝提现：退回余额"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute('SELECT * FROM withdrawals WHERE id = ?', (withdraw_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return {'success': False, 'message': '提现记录不存在'}
            if row['status'] != 'pending':
                conn.rollback()
                return {'success': False, 'message': f"当前状态为 {row['status']}，无法拒绝"}

            wxid = row['wxid']
            amount = float(row['amount'])
            cursor.execute('SELECT balance FROM users WHERE wxid = ?', (wxid,))
            user = cursor.fetchone()
            if not user:
                conn.rollback()
                return {'success': False, 'message': '用户不存在'}

            new_balance = float(user['balance']) + amount
            cursor.execute(
                'UPDATE users SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE wxid = ?',
                (new_balance, wxid),
            )
            cursor.execute(
                '''UPDATE withdrawals SET status = 'rejected', remark = ?, processed_at = CURRENT_TIMESTAMP
                   WHERE id = ?''',
                (remark or '管理员拒绝', withdraw_id),
            )
            cursor.execute(
                '''INSERT INTO transactions (wxid, type, amount, balance_after, description)
                   VALUES (?, 'refund', ?, ?, ?)''',
                (wxid, amount, new_balance, f'提现#{withdraw_id}被拒绝退回'),
            )
            conn.commit()
            return {'success': True, 'wxid': wxid, 'amount': amount}
        except Exception as e:
            conn.rollback()
            logger.error('拒绝提现失败: %s', e)
            return {'success': False, 'message': str(e)}

    def complete_withdrawal(self, withdraw_id, remark=None):
        """审核通过并完成提现（管理员线下转账后标记）"""
        row = self.get_withdrawal(withdraw_id)
        if not row:
            return {'success': False, 'message': '提现记录不存在'}
        if row['status'] != 'pending':
            return {'success': False, 'message': f"当前状态为 {row['status']}，无法通过"}

        self.execute_query(
            '''UPDATE withdrawals SET status = 'completed', remark = ?, processed_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (remark or '管理员已线下转账', withdraw_id),
        )
        logger.info('提现完成: id=%s wxid=%s amount=%.2f', withdraw_id, row['wxid'], row['amount'])
        return {'success': True, 'wxid': row['wxid'], 'amount': float(row['amount'])}

    def settle_order_on_receipt(self, order_no, wxid=None):
        """
        确认收货后结算：将预估返利 user_rebate 发放到用户可提现余额
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute('SELECT * FROM orders WHERE order_no = ?', (order_no,))
            order = cursor.fetchone()
            if not order:
                conn.rollback()
                return {'success': False, 'message': '订单不存在，请检查订单号'}

            if wxid and order['wxid'] != wxid:
                conn.rollback()
                return {'success': False, 'message': '该订单不属于您，无法确认收货'}

            if order['order_status'] == 'settled':
                conn.rollback()
                return {'success': False, 'message': '该订单推广奖励已发放，请勿重复确认'}

            if order['order_status'] == 'failed':
                conn.rollback()
                return {'success': False, 'message': '该订单已失效'}

            if not self.is_order_rebate_eligible(order):
                conn.rollback()
                return {
                    'success': False,
                    'message': '该订单非机器人转链记录，不参与返利结算（如自动发单链接下单）',
                }

            rebate = float(order['user_rebate'] or 0)
            owner_wxid = order['wxid']

            cursor.execute('SELECT balance FROM users WHERE wxid = ?', (owner_wxid,))
            user = cursor.fetchone()
            if not user:
                conn.rollback()
                return {'success': False, 'message': '用户不存在'}

            new_balance = float(user['balance']) + rebate
            cursor.execute(
                'UPDATE users SET balance = ?, total_earnings = total_earnings + ?, updated_at = CURRENT_TIMESTAMP WHERE wxid = ?',
                (new_balance, rebate if rebate > 0 else 0, owner_wxid),
            )
            cursor.execute(
                '''UPDATE orders SET order_status = 'settled', updated_at = CURRENT_TIMESTAMP WHERE order_no = ?''',
                (order_no,),
            )
            if rebate > 0:
                cursor.execute(
                    '''INSERT INTO transactions (wxid, type, amount, balance_after, description, related_order_no)
                       VALUES (?, 'rebate', ?, ?, ?, ?)''',
                    (owner_wxid, rebate, new_balance, f'确认收货返利 {order_no}', order_no),
                )
            conn.commit()
            logger.info('订单结算: %s wxid=%s rebate=%.2f', order_no, owner_wxid, rebate)
            return {
                'success': True,
                'order_no': order_no,
                'rebate': rebate,
                'balance': new_balance,
                'product_title': order['product_title'],
                'notify_chat': order['notify_chat'] if 'notify_chat' in order.keys() else None,
                'notify_is_group': bool(order['notify_is_group']) if 'notify_is_group' in order.keys() else False,
                'user_nickname': order['user_nickname'] if 'user_nickname' in order.keys() else None,
            }
        except Exception as e:
            conn.rollback()
            logger.error('订单结算失败: %s', e)
            return {'success': False, 'message': str(e)}

    # ==================== 群聊消息统计操作 ====================

    def increment_group_msg_count(self, group_id):
        """增加群聊消息计数"""
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')

        # 尝试插入或更新
        existing = self.execute_query(
            'SELECT msg_count FROM group_msg_stats WHERE group_id = ? AND hour_key = ?',
            (group_id, hour_key),
            fetch=True
        )

        if existing:
            new_count = existing['msg_count'] + 1
            self.execute_query(
                'UPDATE group_msg_stats SET msg_count = ? WHERE group_id = ? AND hour_key = ?',
                (new_count, group_id, hour_key)
            )
            return new_count
        else:
            self.execute_query(
                'INSERT INTO group_msg_stats (group_id, hour_key, msg_count) VALUES (?, ?, 1)',
                (group_id, hour_key)
            )
            return 1

    def get_group_msg_count(self, group_id):
        """获取当前小时的群聊消息数"""
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')

        result = self.execute_query(
            'SELECT msg_count FROM group_msg_stats WHERE group_id = ? AND hour_key = ?',
            (group_id, hour_key),
            fetch=True
        )

        return result['msg_count'] if result else 0

    # ==================== 统计查询 ====================

    def get_user_stats(self, wxid):
        """获取用户统计信息"""
        user = self.get_user(wxid)
        if not user:
            return None

        return {
            'wxid': user['wxid'],
            'nickname': user['nickname'],
            'balance': user['balance'],
            'total_earnings': user['total_earnings'],
            'total_orders': user['total_orders'],
            'created_at': user['created_at'],
        }

    def get_total_stats(self):
        """获取全局统计信息"""
        total_users = self.execute_query(
            'SELECT COUNT(*) as count FROM users WHERE status = "active"',
            fetch=True
        )

        total_orders = self.execute_query(
            'SELECT COUNT(*) as count FROM orders',
            fetch=True
        )

        total_commission = self.execute_query(
            'SELECT SUM(commission) as total FROM orders WHERE order_status != "failed"',
            fetch=True
        )

        return {
            'total_users': total_users['count'] if total_users else 0,
            'total_orders': total_orders['count'] if total_orders else 0,
            'total_commission': total_commission['total'] if total_commission else 0.0,
        }

    # ==================== 签到相关操作 ====================

    def add_checkin(self, wxid, reward_amount, continuous_days):
        """
        添加签到记录
        :param wxid: 用户微信ID
        :param reward_amount: 奖励金额
        :param continuous_days: 连续签到天数
        :return: True/False
        """
        try:
            from datetime import date
            today = date.today().isoformat()

            self.execute_query(
                '''INSERT INTO checkins (wxid, checkin_date, reward_amount, continuous_days)
                   VALUES (?, ?, ?, ?)''',
                (wxid, today, reward_amount, continuous_days)
            )

            logger.info(f"用户 {wxid} 签到成功，连续{continuous_days}天，奖励{reward_amount:.2f}元")
            return True
        except Exception as e:
            logger.error(f"添加签到记录失败: {e}")
            return False

    def has_checked_in_today(self, wxid):
        """
        检查用户今天是否已签到
        :param wxid: 用户微信ID
        :return: True表示已签到
        """
        from datetime import date
        today = date.today().isoformat()

        result = self.execute_query(
            'SELECT id FROM checkins WHERE wxid = ? AND checkin_date = ?',
            (wxid, today),
            fetch=True
        )

        return result is not None

    def get_continuous_days(self, wxid):
        """
        获取用户连续签到天数
        :param wxid: 用户微信ID
        :return: 连续签到天数
        """
        try:
            from datetime import date, timedelta

            # 获取用户所有签到记录，按日期倒序
            checkins = self.execute_query(
                'SELECT checkin_date FROM checkins WHERE wxid = ? ORDER BY checkin_date DESC',
                (wxid,),
                fetch_all=True
            )

            if not checkins:
                return 0

            # 计算连续天数
            continuous_days = 0
            today = date.today()

            for i, record in enumerate(checkins):
                checkin_date = date.fromisoformat(record['checkin_date'])
                expected_date = today - timedelta(days=i)

                if checkin_date == expected_date:
                    continuous_days += 1
                else:
                    # 中断了，停止计算
                    break

            return continuous_days

        except Exception as e:
            logger.error(f"计算连续签到天数失败: {e}")
            return 0

    def get_user_checkin_stats(self, wxid):
        """
        获取用户签到统计信息
        :param wxid: 用户微信ID
        :return: 签到统计字典
        """
        # 总签到次数
        total_checkins = self.execute_query(
            'SELECT COUNT(*) as count FROM checkins WHERE wxid = ?',
            (wxid,),
            fetch=True
        )

        # 累计签到奖励
        total_reward = self.execute_query(
            'SELECT SUM(reward_amount) as total FROM checkins WHERE wxid = ?',
            (wxid,),
            fetch=True
        )

        # 最长连续签到（简化版：当前连续天数）
        continuous_days = self.get_continuous_days(wxid)

        # 最近一次签到
        last_checkin = self.execute_query(
            'SELECT * FROM checkins WHERE wxid = ? ORDER BY checkin_date DESC LIMIT 1',
            (wxid,),
            fetch=True
        )

        return {
            'total_checkins': total_checkins['count'] if total_checkins else 0,
            'total_reward': total_reward['total'] if total_reward else 0.0,
            'continuous_days': continuous_days,
            'last_checkin': last_checkin,
        }

    def add_pending_notification(self, wxid: str, message: str) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO pending_notifications (wxid, message) VALUES (?, ?)',
            (wxid, message),
        )
        conn.commit()
        return cursor.lastrowid

    def get_pending_notifications(self, wxid: str, limit: int = 5):
        rows = self.execute_query(
            '''
            SELECT id, wxid, message, created_at
            FROM pending_notifications
            WHERE wxid = ? AND delivered_at IS NULL
            ORDER BY id ASC
            LIMIT ?
            ''',
            (wxid, limit),
            fetch=True,
            fetch_all=True,
        )
        return rows or []

    def mark_notifications_delivered(self, ids):
        if not ids:
            return
        placeholders = ','.join('?' for _ in ids)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f'''
            UPDATE pending_notifications
            SET delivered_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders}) AND delivered_at IS NULL
            ''',
            tuple(ids),
        )
        conn.commit()

    # ==================== 管理后台列表查询 ====================

    def admin_dashboard_stats(self):
        """管理后台概览统计"""
        pending = self.execute_query(
            "SELECT COUNT(*) as count FROM withdrawals WHERE status = 'pending'",
            fetch=True,
        )
        total_balance = self.execute_query(
            'SELECT COALESCE(SUM(balance), 0) as total FROM users WHERE status = "active"',
            fetch=True,
        )
        base = self.get_total_stats()
        return {
            **base,
            'pending_withdrawals': pending['count'] if pending else 0,
            'total_user_balance': float(total_balance['total']) if total_balance else 0.0,
        }

    def admin_list_users(self, offset=0, limit=20, search=None):
        where, params = '', []
        if search:
            where = 'WHERE wxid LIKE ? OR nickname LIKE ?'
            q = f'%{search}%'
            params = [q, q]
        total_row = self.execute_query(
            f'SELECT COUNT(*) as count FROM users {where}',
            tuple(params) if params else None,
            fetch=True,
        )
        rows = self.execute_query(
            f'''SELECT id, wxid, nickname, balance, total_earnings, total_orders,
                       status, created_at, updated_at
                FROM users {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            tuple(params + [limit, offset]),
            fetch_all=True,
        )
        return {'total': total_row['count'] if total_row else 0, 'items': rows or []}

    def admin_list_orders(self, offset=0, limit=20, status=None, wxid=None, platform=None):
        clauses, params = [], []
        if status:
            clauses.append('order_status = ?')
            params.append(status)
        if wxid:
            clauses.append('wxid LIKE ?')
            params.append(f'%{wxid}%')
        if platform:
            clauses.append('platform = ?')
            params.append(platform)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        total_row = self.execute_query(
            f'SELECT COUNT(*) as count FROM orders {where}',
            tuple(params) if params else None,
            fetch=True,
        )
        rows = self.execute_query(
            f'''SELECT id, order_no, wxid, platform, product_title, original_price,
                       commission, user_rebate, order_status, platform_order_id,
                       platform_status, created_at, updated_at
                FROM orders {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            tuple(params + [limit, offset]),
            fetch_all=True,
        )
        return {'total': total_row['count'] if total_row else 0, 'items': rows or []}

    def admin_list_withdrawals(self, offset=0, limit=20, status=None, wxid=None):
        clauses, params = [], []
        if status and status != 'all':
            clauses.append('status = ?')
            params.append(status)
        if wxid:
            clauses.append('wxid = ?')
            params.append(wxid)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        total_row = self.execute_query(
            f'SELECT COUNT(*) as count FROM withdrawals {where}',
            tuple(params) if params else None,
            fetch=True,
        )
        rows = self.execute_query(
            f'''SELECT id, wxid, amount, status, payment_method, payment_account,
                       remark, created_at, processed_at
                FROM withdrawals {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            tuple(params + [limit, offset]),
            fetch_all=True,
        )
        return {'total': total_row['count'] if total_row else 0, 'items': rows or []}

    def admin_list_transactions(self, offset=0, limit=20, wxid=None):
        clauses, params = [], []
        if wxid:
            clauses.append('wxid LIKE ?')
            params.append(f'%{wxid}%')
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        total_row = self.execute_query(
            f'SELECT COUNT(*) as count FROM transactions {where}',
            tuple(params) if params else None,
            fetch=True,
        )
        rows = self.execute_query(
            f'''SELECT id, wxid, type, amount, balance_after, description,
                       related_order_no, created_at
                FROM transactions {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            tuple(params + [limit, offset]),
            fetch_all=True,
        )
        return {'total': total_row['count'] if total_row else 0, 'items': rows or []}

    def admin_list_checkins(self, offset=0, limit=20, wxid=None):
        clauses, params = [], []
        if wxid:
            clauses.append('wxid LIKE ?')
            params.append(f'%{wxid}%')
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        total_row = self.execute_query(
            f'SELECT COUNT(*) as count FROM checkins {where}',
            tuple(params) if params else None,
            fetch=True,
        )
        rows = self.execute_query(
            f'''SELECT id, wxid, checkin_date, reward_amount, continuous_days, created_at
                FROM checkins {where}
                ORDER BY checkin_date DESC, id DESC LIMIT ? OFFSET ?''',
            tuple(params + [limit, offset]),
            fetch_all=True,
        )
        return {'total': total_row['count'] if total_row else 0, 'items': rows or []}

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
