#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
五子棋游戏 (Gobang)
基于 Python + Tkinter 实现
功能：双人对战、胜负判断、悔棋、重新开始
"""

import tkinter as tk
from tkinter import messagebox
from tkinter import font as tkfont
import traceback
import sys
import os


# ============================================================
# 全局异常处理：将所有未捕获的异常记录到文件
# ============================================================
ERROR_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gobang_error.log")

def global_exception_handler(exc_type, exc_value, exc_tb):
    """全局异常处理钩子，将异常信息写入日志文件"""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"【全局异常】{exc_type.__name__}\n")
        f.write(error_msg)
        f.write("\n" + "=" * 60 + "\n")
    # 同时也打印到控制台
    print(error_msg, file=sys.stderr)

# 注册全局异常钩子
sys.excepthook = global_exception_handler


class GobangGame:
    """五子棋游戏类"""

    # 棋盘大小
    BOARD_SIZE = 15
    # 格子大小（像素）
    CELL_SIZE = 40
    # 棋子半径
    PIECE_RADIUS = 16
    # 棋盘边距
    MARGIN = 30
    # 棋盘总宽度
    BOARD_WIDTH = MARGIN * 2 + CELL_SIZE * (BOARD_SIZE - 1)

    # 颜色定义
    COLOR_BOARD_BG = "#DEB887"  # 棋盘底色（burlywood）
    COLOR_BOARD_LINE = "#000000"  # 棋盘线
    COLOR_BLACK = "#000000"  # 黑子
    COLOR_WHITE = "#FFFFFF"  # 白子
    COLOR_STAR = "#000000"  # 星位标记
    COLOR_INFO_BG = "#F5F5DC"  # 信息面板背景
    COLOR_BTN_BG = "#8B7355"  # 按钮背景
    COLOR_BTN_FG = "#FFFFFF"  # 按钮文字
    COLOR_HINT = "#FF4500"  # 提示色（最后一个落子标记）

    def __init__(self, root):
        self.root = root
        self.root.title("五子棋 - Gobang")
        self.root.resizable(False, False)

        # 替换 Tkinter 默认的异常处理方法，将错误写入日志
        root.report_callback_exception = self._tk_callback_exception

        # 游戏状态
        self.board = [[0] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        # 0: 空, 1: 黑子, 2: 白子
        self.current_player = 1  # 1: 黑棋先手, 2: 白棋
        self.game_over = False
        self.move_history = []  # 落子历史
        self.last_move = None  # 最后一步落子位置

        # 创建界面
        self._create_widgets()

        # 绑定键盘事件
        self.root.bind("<Control-z>", lambda e: self.undo_move())
        self.root.bind("<Control-r>", lambda e: self.reset_game())

    def _tk_callback_exception(self, exc, val, tb):
        """覆盖 Tkinter 默认的回调异常处理方法，将错误写入文件而不是只打印到控制台"""
        error_msg = "".join(traceback.format_exception(exc, val, tb))
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("【Tkinter 回调异常】\n")
            f.write(error_msg)
            f.write("\n" + "=" * 60 + "\n")
        # 弹出错误对话框给用户
        try:
            messagebox.showerror("程序出错", f"发生了未预期的错误，详情已记录到：\n{ERROR_LOG_FILE}\n\n{exc.__name__}: {val}")
        except Exception:
            pass

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = tk.Frame(self.root, bg=self.COLOR_INFO_BG)
        main_frame.pack(padx=10, pady=10)

        # ---- 左侧：棋盘 ----
        self.canvas = tk.Canvas(
            main_frame,
            width=self.BOARD_WIDTH,
            height=self.BOARD_WIDTH,
            bg=self.COLOR_BOARD_BG,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))

        # 绘制棋盘
        self._draw_board()

        # 绑定鼠标点击事件
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)

        # ---- 右侧：信息面板 ----
        info_frame = tk.Frame(main_frame, bg=self.COLOR_INFO_BG, width=180)
        info_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        info_frame.pack_propagate(False)

        # 标题
        title_font = tkfont.Font(family="微软雅黑", size=16, weight="bold")
        tk.Label(
            info_frame,
            text="五 子 棋",
            font=title_font,
            bg=self.COLOR_INFO_BG,
            fg="#8B4513",
        ).pack(pady=(20, 15))

        # 当前玩家提示
        self.turn_label = tk.Label(
            info_frame,
            text="当前：● 黑棋走",
            font=("微软雅黑", 13),
            bg=self.COLOR_INFO_BG,
            fg="#333333",
        )
        self.turn_label.pack(pady=10)

        # 棋子数量统计
        self.stats_label = tk.Label(
            info_frame,
            text="黑棋：0  白棋：0",
            font=("微软雅黑", 11),
            bg=self.COLOR_INFO_BG,
            fg="#666666",
        )
        self.stats_label.pack(pady=5)

        # 分隔线
        tk.Frame(info_frame, height=2, bg="#CCCCCC").pack(fill=tk.X, pady=15, padx=20)

        # 按钮样式
        btn_font = tkfont.Font(family="微软雅黑", size=11)

        # 重新开始按钮
        tk.Button(
            info_frame,
            text="🔄 重新开始",
            font=btn_font,
            bg=self.COLOR_BTN_BG,
            fg=self.COLOR_BTN_FG,
            activebackground="#A0896B",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            command=self.reset_game,
        ).pack(pady=5, fill=tk.X, padx=10)

        # 悔棋按钮
        tk.Button(
            info_frame,
            text="↩ 悔棋 (Ctrl+Z)",
            font=btn_font,
            bg=self.COLOR_BTN_BG,
            fg=self.COLOR_BTN_FG,
            activebackground="#A0896B",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            command=self.undo_move,
        ).pack(pady=5, fill=tk.X, padx=10)

        # 帮助按钮
        tk.Button(
            info_frame,
            text="❓ 游戏说明",
            font=btn_font,
            bg=self.COLOR_BTN_BG,
            fg=self.COLOR_BTN_FG,
            activebackground="#A0896B",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            command=self._show_help,
        ).pack(pady=5, fill=tk.X, padx=10)

        # 底部版本信息
        tk.Label(
            info_frame,
            text="v1.0 | Python + Tkinter",
            font=("微软雅黑", 8),
            bg=self.COLOR_INFO_BG,
            fg="#AAAAAA",
        ).pack(side=tk.BOTTOM, pady=10)

    def _draw_board(self):
        """绘制棋盘网格、星位"""
        canvas = self.canvas
        size = self.BOARD_SIZE
        cell = self.CELL_SIZE
        margin = self.MARGIN

        # 绘制网格线
        for i in range(size):
            # 横线
            x1 = margin
            y1 = margin + i * cell
            x2 = margin + (size - 1) * cell
            y2 = y1
            canvas.create_line(x1, y1, x2, y2, fill=self.COLOR_BOARD_LINE, width=1)

            # 竖线
            x1 = margin + i * cell
            y1 = margin
            x2 = x1
            y2 = margin + (size - 1) * cell
            canvas.create_line(x1, y1, x2, y2, fill=self.COLOR_BOARD_LINE, width=1)

        # 绘制星位（天元 + 四个星位）
        star_positions = [
            (3, 3),
            (3, 11),
            (7, 7),  # 天元
            (11, 3),
            (11, 11),
        ]
        star_radius = 4
        for row, col in star_positions:
            x = margin + col * cell
            y = margin + row * cell
            canvas.create_oval(
                x - star_radius,
                y - star_radius,
                x + star_radius,
                y + star_radius,
                fill=self.COLOR_STAR,
                outline="",
            )

    def _get_board_pos(self, x, y):
        """将像素坐标转换为棋盘行列坐标"""
        margin = self.MARGIN
        cell = self.CELL_SIZE

        col = round((x - margin) / cell)
        row = round((y - margin) / cell)

        # 检查是否在有效范围内
        if 0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE:
            # 检查点击是否在交叉点附近
            cx = margin + col * cell
            cy = margin + row * cell
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist <= self.CELL_SIZE * 0.45:
                return row, col
        return None, None

    def _on_click(self, event):
        """鼠标点击事件处理"""
        try:
            if self.game_over:
                return

            row, col = self._get_board_pos(event.x, event.y)
            if row is None or col is None:
                return

            # 检查该位置是否已有棋子
            if self.board[row][col] != 0:
                return

            # 落子
            self._place_piece(row, col)
        except Exception as e:
            error_detail = traceback.format_exc()
            # 同时写入日志
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"【点击回调异常】{e}\n{error_detail}\n")
            messagebox.showerror("错误", f"点击事件异常：{e}")

    def _on_mouse_move(self, event):
        """鼠标移动事件 - 显示悬停预览"""
        try:
            row, col = self._get_board_pos(event.x, event.y)
            if row is not None and col is not None and self.board[row][col] == 0 and not self.game_over:
                self.canvas.config(cursor="hand2")
            else:
                self.canvas.config(cursor="")
        except Exception:
            pass  # 鼠标移动事件过于频繁，忽略异常

    def _place_piece(self, row, col):
        """在指定位置落子"""
        player = self.current_player
        self.board[row][col] = player
        self.move_history.append((row, col, player))
        self.last_move = (row, col)

        # 绘制棋子
        self._draw_piece(row, col, player)

        # 标记最后一步
        self._mark_last_move(row, col)

        # 更新统计
        self._update_stats()

        # 检查胜负
        if self._check_win(row, col, player):
            self.game_over = True
            winner = "● 黑棋" if player == 1 else "○ 白棋"
            self.turn_label.config(text=f"🎉 {winner} 获胜！")
            messagebox.showinfo("游戏结束", f"{winner} 获胜！🎉")
            return

        # 检查平局
        if self._is_draw():
            self.game_over = True
            self.turn_label.config(text="🤝 平局！")
            messagebox.showinfo("游戏结束", "棋盘已满，平局！")
            return

        # 切换玩家
        self.current_player = 3 - player  # 1->2, 2->1
        player_text = "● 黑棋" if self.current_player == 1 else "○ 白棋"
        self.turn_label.config(text=f"当前：{player_text}走")

    def _draw_piece(self, row, col, player):
        """绘制棋子"""
        try:
            x = self.MARGIN + col * self.CELL_SIZE
            y = self.MARGIN + row * self.CELL_SIZE
            r = self.PIECE_RADIUS

            # 绘制阴影效果
            shadow_offset = 2
            self.canvas.create_oval(
                x - r + shadow_offset,
                y - r + shadow_offset,
                x + r + shadow_offset,
                y + r + shadow_offset,
                fill="#C0B090",
                outline="",
                tags="shadow",
            )

            # 绘制棋子主体
            color = self.COLOR_BLACK if player == 1 else self.COLOR_WHITE
            outline = "#333333" if player == 1 else "#CCCCCC"
            self.canvas.create_oval(
                x - r,
                y - r,
                x + r,
                y + r,
                fill=color,
                outline=outline,
                width=1.5,
                tags="piece",
            )

            # 添加高光效果
            if player == 1:
                highlight_r = r * 0.35
                self.canvas.create_oval(
                    x - highlight_r - 2,
                    y - highlight_r - 2,
                    x - 2,
                    y - 2,
                    fill="#808080",
                    outline="",
                    tags="piece",
                )
            else:
                highlight_r = r * 0.4
                self.canvas.create_oval(
                    x - highlight_r - 1,
                    y - highlight_r - 1,
                    x - 1,
                    y - 1,
                    fill="#E8E8E8",
                    outline="",
                    tags="piece",
                )

            # 白子加边线内圈
            if player == 2:
                inner_r = r * 0.85
                self.canvas.create_oval(
                    x - inner_r,
                    y - inner_r,
                    x + inner_r,
                    y + inner_r,
                    outline="#E0E0E0",
                    width=1,
                    tags="piece",
                )
        except Exception as e:
            # 绘制棋子出错时记录日志
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"【绘制棋子异常】row={row}, col={col}, player={player}: {e}\n{traceback.format_exc()}\n")
            raise  # 重新抛出，让上层处理

    def _mark_last_move(self, row, col):
        """标记最后落子的位置"""
        # 清除旧的标记
        self.canvas.delete("last_move_mark")

        x = self.MARGIN + col * self.CELL_SIZE
        y = self.MARGIN + row * self.CELL_SIZE

        player = self.board[row][col]
        # 黑子上用白色标记，白子上用橙色标记
        if player == 1:
            color = "#FFFFFF"
        elif player == 2:
            color = self.COLOR_HINT
        else:
            color = "#FF0000"
        mark_size = 5

        self.canvas.create_oval(
            x - mark_size,
            y - mark_size,
            x + mark_size,
            y + mark_size,
            fill=color,
            outline="",
            tags="last_move_mark",
        )

    def _check_win(self, row, col, player):
        """检查是否五子连珠（核心算法）"""
        # 四个方向向量: 水平, 垂直, 主对角线, 副对角线
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

        for dr, dc in directions:
            count = 1  # 当前棋子

            # 正方向延伸
            r, c = row + dr, col + dc
            while 0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE and self.board[r][c] == player:
                count += 1
                r += dr
                c += dc

            # 反方向延伸
            r, c = row - dr, col - dc
            while 0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE and self.board[r][c] == player:
                count += 1
                r -= dr
                c -= dc

            # 检查是否达到五子连珠
            if count >= 5:
                return True

        return False

    def _is_draw(self):
        """检查是否平局（棋盘已满）"""
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                if self.board[row][col] == 0:
                    return False
        return True

    def _update_stats(self):
        """更新棋子统计信息"""
        black_count = sum(row.count(1) for row in self.board)
        white_count = sum(row.count(2) for row in self.board)
        self.stats_label.config(
            text=f"● 黑棋：{black_count}  ○ 白棋：{white_count}"
        )

    def undo_move(self):
        """悔棋功能"""
        try:
            if self.game_over:
                # 如果游戏已结束，先询问
                if not messagebox.askyesno("悔棋", "游戏已结束，是否悔棋继续？"):
                    return
                self.game_over = False

            if not self.move_history:
                messagebox.showinfo("提示", "没有可以悔棋的步骤")
                return

            # 可以连续悔棋，每次悔一步
            row, col, player = self.move_history.pop()
            self.board[row][col] = 0
            self.current_player = player

            # 重绘棋盘（清空所有棋子重绘）
            self.canvas.delete("piece", "shadow", "last_move_mark")
            for r in range(self.BOARD_SIZE):
                for c in range(self.BOARD_SIZE):
                    if self.board[r][c] != 0:
                        self._draw_piece(r, c, self.board[r][c])

            # 标记新的最后一步
            if self.move_history:
                last = self.move_history[-1]
                self.last_move = (last[0], last[1])
                self._mark_last_move(last[0], last[1])
            else:
                self.last_move = None

            # 更新显示
            player_text = "● 黑棋" if self.current_player == 1 else "○ 白棋"
            self.turn_label.config(text=f"当前：{player_text}走")
            self._update_stats()
        except Exception as e:
            error_detail = traceback.format_exc()
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"【悔棋回调异常】{e}\n{error_detail}\n")
            messagebox.showerror("错误", f"悔棋事件异常：{e}")

    def reset_game(self):
        """重新开始游戏"""
        try:
            if self.move_history:
                if not messagebox.askyesno("重新开始", "确定要重新开始吗？当前进度将丢失。"):
                    return

            # 重置状态
            self.board = [[0] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
            self.current_player = 1
            self.game_over = False
            self.move_history = []
            self.last_move = None

            # 清空画布并重绘棋盘
            self.canvas.delete("all")
            self._draw_board()

            # 更新显示
            self.turn_label.config(text="当前：● 黑棋走")
            self._update_stats()
        except Exception as e:
            error_detail = traceback.format_exc()
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"【重置回调异常】{e}\n{error_detail}\n")
            messagebox.showerror("错误", f"重置事件异常：{e}")

    def _show_help(self):
        """显示游戏说明"""
        help_text = """
🎮 五子棋游戏说明

📌 基本规则
• 双人对战，黑棋先走，白棋后走
• 轮流在棋盘交叉点落子
• 先在横、竖、斜任一方向上
  连成五子的一方获胜

🖱 操作方式
• 点击棋盘交叉点落子
• 「重新开始」按钮重置游戏
• 「悔棋」按钮撤销上一步
• 快捷键：Ctrl+Z 悔棋
  Ctrl+R 重新开始

💡 提示
• 棋盘上的●标记表示最后
  一步落子位置
• 鼠标悬停位置会变成
  手型光标
        """
        messagebox.showinfo("游戏说明", help_text)


def main():
    """主函数"""
    # 将 stderr 也重定向到日志文件
    sys.stderr = open(ERROR_LOG_FILE, "a", encoding="utf-8")
    
    root = tk.Tk()
    # 设置窗口图标（如果有）
    try:
        root.iconbitmap("gobang.ico")
    except Exception:
        pass
    app = GobangGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
