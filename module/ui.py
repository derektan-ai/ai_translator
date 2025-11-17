# pylint: disable=too-many-lines
# pylint: disable=no-name-in-module  # PyQt5模块导入问题在实际运行中不存在
"""
UI模块
实现半透明字幕窗与翻译控制按钮一体化
具备原文和译文并列显示、可调窗口大小、动态光效边框、动态透明度管理等功能
"""
import sys
import os
import logging
import configparser
from dataclasses import dataclass, field
from PyQt5.QtWidgets import (
    QWidget,
    QApplication,
    QLabel,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QFrame,
)
from PyQt5.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QConicalGradient,
    QBrush,
    QPen,
    QIcon,
    QPixmap,
)
from PyQt5.QtCore import (
    Qt,
    QPoint,
    QRect,
    QRectF,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QThread,
    pyqtSignal,
)
from .config import Config
from .translator_unit import TranslatorUnit
from .info import INFO
from .select_language import LanguageSelectionDialog
from .result_recorder import ResultRecorder
from .message_center import message_center

# pylint: disable=too-many-instance-attributes  # 数据类需要定义所有控件属性
@dataclass
class ControlWidgets:
    """控件属性分组"""
    source_lang_label: None = None
    source_language: None = None
    lang_map_source: None = None
    target_lang_label: None = None
    target_language: None = None
    lang_map_target: None = None
    toggle_button: None = None
    format_label: None = None
    convert_button: None = None
    output_format: None = None
    format_options: None = None
    minimize_button: None = None
    maximize_button: None = None
    close_button: None = None
    control_frame: QFrame = None
    control_layout: QHBoxLayout = None
    middle_area: None = None

@dataclass
class WindowState:
    """窗口状态属性分组"""
    original_rect: None = None
    original_pos: None = None
    normal_geometry: None = None
    is_maximized: bool = False

@dataclass
class ResizeConfig:
    """尺寸调整属性分组"""
    resizing: bool = False
    resize_direction: None = None
    min_width: int = 400
    min_height: int = 150
    border_width: int = 20

@dataclass
class AnimationConfig:
    """动画属性分组"""
    animation_progress: int = 0
    border_animation_duration: int = 5000
    animation_timer: QTimer = None
    is_animation_active: bool = False

@dataclass
class TranslatorState:
    """翻译状态属性分组"""
    is_running: bool = False
    translator_app: None = None
    realtime_text: str = ""

@dataclass
class OpacityConfig:
    """透明度属性分组"""
    base_opacity: float = 0.6       # 基础状态
    hover_opacity: float = 0.8      # 鼠标悬停
    translating_opacity: float = 0.8 # 翻译中（与hover数值相同，避免误解）
    idle_opacity: float = 0.3       # 闲置状态

@dataclass
class DragConfig:
    """拖动属性分组"""
    dragging: bool = False
    offset: QPoint = field(default_factory=QPoint)

@dataclass
class TimerConfig:
    """计时器属性分组"""
    idle_timer: QTimer = None
    idle_delay: int = 300000

@dataclass
class ThemeConfig:
    """主题颜色属性分组"""
    dark: QColor = None
    blue: QColor = None
    light_blue: QColor = None
    gray: QColor = None
    light_gray: QColor = None

@dataclass
class CursorConfig:
    """光标跟踪属性分组"""
    last_cursor: None = None
    last_direction: None = None

@dataclass
class BackgroundConfig:
    """背景绘制相关属性分组"""
    path: None = None
    rect: None = None

# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes  # 功能需要，已通过数据类合理分组
class UI(QWidget):
    """实现程序可操作界面的类"""
    def __init__(self, *args, **kwargs):
        """初始化UI，添加网络错误处理相关设置"""
        super().__init__(*args, **kwargs)

        # 初始化属性分组
        self.widgets = ControlWidgets()
        self.window = WindowState()
        self.resize_config = ResizeConfig()
        self.animation = AnimationConfig()
        self.translator = TranslatorState()
        self.opacity = OpacityConfig()
        self.drag = DragConfig()
        self.timers = TimerConfig()
        self.theme = ThemeConfig()
        self.cursor = CursorConfig()
        self.background = BackgroundConfig()

        # 记录器相关属性
        self.result_recorder = None

        # 语言相关属性
        self.language = None

        # 日志相关属性
        self.logger = logging.getLogger(__name__)

        # 线程相关属性
        self._translation_thread = None

        # -------------- 初始化逻辑 --------------
        # 加载语言设置
        self.language = Config.load_language_setting()
        # 如果是首次启动，显示语言选择对话框
        first_run = not os.path.exists(Config.LANGUAGE_FILE)
        if first_run:
            self.show_language_dialog()
            # 重新加载语言设置，确保获取到用户选择的语言
            self.language = Config.load_language_setting()

        # 定义主题颜色
        self.theme.dark = QColor(30, 35, 45)
        self.theme.blue = QColor(66, 135, 245)
        self.theme.light_blue = QColor(100, 160, 255)
        self.theme.gray = QColor(50, 55, 65)
        self.theme.light_gray = QColor(70, 75, 85)

        # 控制栏自动变暗定时器
        self.timers.idle_timer = QTimer(self)
        self.timers.idle_timer.setSingleShot(True)
        self.timers.idle_timer.timeout.connect(self.enter_idle_state)

        # 初始化实时文本
        self.translator.realtime_text = INFO.get("subtitle_area", self.language)

        # 初始化结果记录器（确保在语言设置之后）
        self._init_result_recorder()

        # 初始化UI和动画
        self.initUI()
        self.setup_animation()

        # 设置窗口图标
        self.set_window_icon()

        # 初始化控制区样式
        self.widgets.control_frame.setStyleSheet("background-color: transparent;")

        # 初始化中间区域光标探测器
        self._setup_middle_area()

        # 对于首次运行，确保窗口显示
        if first_run:
            self.show()

    def _initialize_all_attributes(self):
        """初始化所有属性为None或默认值"""
        # 重置控件属性
        self.widgets = ControlWidgets()

        # 重置窗口状态变量
        self.window = WindowState()

        # 重置窗口大小调整相关变量
        self.resize_config = ResizeConfig()

        # 重置边框动画参数
        self.animation = AnimationConfig()

        # 重置状态变量
        self.translator = TranslatorState()

        # 重置透明度设置
        self.opacity = OpacityConfig()

        # 重置窗口拖动变量
        self.drag = DragConfig()

        # 重置闲置计时器
        self.timers = TimerConfig()

        # 重置语言属性
        self.language = None

        # 重置主题颜色
        self.theme = ThemeConfig()

        # 重置光标跟踪属性
        self.cursor = CursorConfig()

        # 重置背景绘制属性
        self.background = BackgroundConfig()

    def _init_result_recorder(self):
        """初始化结果记录器"""
        # 假设源语言和目标语言有默认值，根据实际配置调整
        source_lang = "auto"
        target_lang = Config.TRANSLATE_TARGET  # 使用正确的配置属性名

        # 准备格式配置
        format_config = {
            'output_format': INFO.get("original_translation_parallel", self.language),
            'format_options': {
                INFO.get("original_translation_parallel", self.language):
                    INFO.get("original_translation_parallel", self.language),
                INFO.get("original_translation_separate", self.language):
                    INFO.get("original_translation_separate", self.language)
            }
        }

        self.result_recorder = ResultRecorder(
            source_lang=source_lang,
            target_lang=target_lang,
            logger=self.logger,
            format_config=format_config
        )

    def _setup_language_and_first_run(self):
        """设置语言和处理首次运行逻辑"""
        self.language = Config.load_language_setting()
        first_run = not os.path.exists(Config.LANGUAGE_FILE)

        if first_run:
            self.show_language_dialog()
            self.language = Config.load_language_setting()
            self.show()  # 确保窗口显示

        # 初始化实时文本
        self.translator.realtime_text = INFO.get("subtitle_area", self.language)

    def _define_theme_colors(self):
        """定义主题颜色"""
        self.theme.dark = QColor(30, 35, 45)
        self.theme.blue = QColor(66, 135, 245)
        self.theme.light_blue = QColor(100, 160, 255)
        self.theme.gray = QColor(50, 55, 65)
        self.theme.light_gray = QColor(70, 75, 85)

    def _setup_window_behavior_variables(self):
        """设置窗口行为相关变量"""
        # 控制栏自动变暗定时器
        self.timers.idle_timer = QTimer(self)
        self.timers.idle_timer.setSingleShot(True)
        self.timers.idle_timer.timeout.connect(self.enter_idle_state)

    def _setup_middle_area(self):
        """设置中间区域光标探测器"""
        self.widgets.middle_area = QFrame(self)
        self.widgets.middle_area.setAttribute(Qt.WA_TranslucentBackground)
        self.widgets.middle_area.setStyleSheet("background-color: transparent;")
        self.widgets.middle_area.setMouseTracking(True)
        self.widgets.middle_area.lower()

        # 鼠标进入中间区域时强制设置为箭头光标
        def on_middle_enter(e):
            if not self.resize_config.resizing and not self.drag.dragging:
                if self.cursor.last_cursor != Qt.ArrowCursor:
                    self.setCursor(Qt.ArrowCursor)
                    self.cursor.last_cursor = Qt.ArrowCursor
                    self.cursor.last_direction = None
            QFrame.enterEvent(self.widgets.middle_area, e)

        self.widgets.middle_area.enterEvent = on_middle_enter
        self.adjust_middle_area()

    def on_network_error(self, message, translator=None,
                         message_center_instance=None, update_ui=True):
        """处理网络错误，自动停止并显示提示

        Args:
            message: 错误消息内容
            translator: 翻译器实例，用于测试时注入模拟
            message_center_instance: 消息中心实例，用于测试时注入模拟
            update_ui: 是否更新UI状态，默认为True
        """
        # 使用提供的message_center或默认导入
        if message_center_instance is not None:
            current_message_center = message_center_instance
        else:
            current_message_center = message_center

        # 显示错误消息
        try:
            current_message_center.show_critical(
                INFO.get("network_error", self.language),
                message,
                parent=self
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # 如果消息中心调用失败，记录错误但不中断流程
            pass

        # 自动停止翻译
        target_translator = translator if translator is not None else self.translator
        try:
            if hasattr(target_translator, 'is_running') and target_translator.is_running:
                # 检查stop_translation方法是否存在于当前对象或翻译器对象中
                if hasattr(self, 'stop_translation'):
                    self.stop_translation()
                elif hasattr(target_translator, 'stop_translation'):
                    target_translator.stop_translation()
        except Exception:  # pylint: disable=broad-exception-caught
            # 如果停止翻译失败，记录错误但不中断流程
            pass

        # 更新UI状态
        if update_ui:
            try:
                self.update_ui_state(False)
            except Exception:  # pylint: disable=broad-exception-caught
                # 如果更新UI状态失败，记录错误但不中断流程
                pass

    def show_language_dialog(self):
        """显示语言选择对话框"""
        dialog = LanguageSelectionDialog(self)
        if dialog.exec_():
            selected_lang = dialog.get_selected_language()
            # 确保配置被正确保存
            Config.save_language_setting(selected_lang)
            # 验证保存是否成功
            if os.path.exists(Config.LANGUAGE_FILE):
                try:
                    # 使用configparser读取ini文件
                    config = configparser.ConfigParser()
                    config.read(Config.LANGUAGE_FILE, encoding='utf-8')
                    saved_lang = config.get('Settings', 'language', fallback=None)

                    if saved_lang == selected_lang:
                        print(INFO.get("language_saved_success", self.language)\
                            .format(lang=selected_lang))
                        # 重启程序以应用语言设置
                        python = sys.executable
                        os.execl(python, python, *sys.argv)
                    else:
                        print(INFO.get("language_save_verify_failed", self.language))
                except (configparser.Error, UnicodeDecodeError) as e:
                    print(INFO.get("language_verify_error", self.language).format(error=str(e)))
            else:
                print(INFO.get("language_file_not_created", self.language)\
                    .format(path=Config.LANGUAGE_FILE))

    def adjust_middle_area(self, control_height=40):
        """调整中间区域探测器的大小和位置，使其位于border和width-border之间，且不覆盖控件区域

        Args:
            control_height: 控件区域高度，默认40像素
        """
        # 使用resize_config的属性
        border_width = self.resize_config.border_width

        # 检查窗口是否足够大
        if (self.width() > 2 * border_width and
            self.height() > control_height + border_width):
            # 计算中间区域的几何参数
            x = border_width
            y = control_height
            width = self.width() - 2 * border_width
            height = self.height() - control_height - border_width

            # 设置中间区域的几何属性并显示
            self.widgets.middle_area.setGeometry(x, y, width, height)
            self.widgets.middle_area.show()
        else:
            # 窗口太小时隐藏中间区域
            self.widgets.middle_area.hide()

    # pylint: disable=invalid-name
    def resizeEvent(self, event):
        """窗口大小改变时调整中间区域和控制区域"""
        self.adjust_middle_area()
        # 同时更新控制区域大小
        self.widgets.control_frame.setGeometry(0, 0, self.width(), 40)
        super().resizeEvent(event)

    def get_resize_direction(self, pos, resize_config=None, check_controls=True):
        """根据鼠标位置确定调整窗口大小的方向，优化边界判断

        Args:
            pos: 鼠标位置
            resize_config: ResizeConfig实例，用于测试时注入模拟
            check_controls: 是否检查控件区域，默认为True

        Returns:
            调整方向字符串或None
        """
        # 使用提供的resize_config或默认的self.resize_config
        if resize_config is None:
            resize_config = self.resize_config

        x, y = pos.x(), pos.y()
        width, height = self.width(), self.height()
        border_width = resize_config.border_width

        # 检查控件区域，控件区域内不触发调整
        if check_controls and hasattr(self, 'is_mouse_over_controls'):
            if self.is_mouse_over_controls(pos):
                return None

        # 检查是否在窗口中部区域
        if (border_width < x < width - border_width and
            border_width < y < height - border_width):
            return None  # 明确返回None表示中部区域

        # 边缘区域检测
        left_edge = x <= border_width
        right_edge = x >= width - border_width
        top_edge = y <= border_width
        bottom_edge = y >= height - border_width

        # 排除角落区域的边缘检测（避免重叠判断）
        in_horizontal_only = (left_edge or right_edge) and not (top_edge or bottom_edge)
        in_vertical_only = (top_edge or bottom_edge) and not (left_edge or right_edge)

        # 判断调整方向
        if in_horizontal_only and border_width < y < height - border_width:
            return 'horizontal'
        if in_vertical_only and border_width < x < width - border_width:
            return 'vertical'
        if (left_edge and top_edge) or (right_edge and bottom_edge):
            return 'b_diagonal'
        return 'f_diagonal'

    @staticmethod
    def get_meipass(sys_module=sys):
        """安全获取MEIPASS路径的辅助方法

        Args:
            sys_module: sys模块，用于测试时注入模拟

        Returns:
            MEIPASS路径或None
        """
        return getattr(sys_module, '_MEIPASS', None)

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def set_window_icon(self, icon_name="ai_translator.ico",
                      os_module=os, sys_module=sys,
                      qicon_class=QIcon, qpixmap_class=QPixmap):
        """设置窗口图标，支持打包后访问图标文件，增加调试信息

        Args:
            icon_name: 图标文件名
            os_module: os模块，用于测试时注入模拟
            sys_module: sys模块，用于测试时注入模拟
            qicon_class: QIcon类，用于测试时注入模拟
            qpixmap_class: QPixmap类，用于测试时注入模拟
        """
        icon_path = None

        # 检查是否为打包后的环境
        if getattr(sys_module, 'frozen', False):
            # 打包后使用临时目录路径
            base_path = self.get_meipass(sys_module)
            if base_path:
                icon_path = os_module.path.join(base_path, icon_name)

        # 如果不是打包环境或打包环境下未找到图标，尝试当前目录
        if icon_path is None or not os_module.path.exists(icon_path):
            current_dir = os_module.path.dirname(
                os_module.path.abspath(
                    sys_module.executable if getattr(sys_module, 'frozen', False) else __file__
                )
            )
            icon_path = os_module.path.join(current_dir, icon_name)

        # 无论是否找到，都避免程序闪退
        try:
            if os_module.path.exists(icon_path):
                self.setWindowIcon(qicon_class(qpixmap_class(icon_path)))
        except (IOError, RuntimeError) as e:
            print(INFO.get("window_icon_error", self.language).format(error=str(e)))

    def set_cursor_based_on_position(self, pos):
        """优化光标设置逻辑，确保实时更新，优先处理控件区域"""
        # 检查鼠标是否在任何控件上
        if self.is_mouse_over_controls(pos):
            if self.cursor.last_cursor != Qt.ArrowCursor:
                self.setCursor(Qt.ArrowCursor)
                self.cursor.last_cursor = Qt.ArrowCursor
                self.cursor.last_direction = None
            # 如果在控件上，取消调整状态
            if self.resize_config.resizing:
                self.resize_config.resizing = False
            return

        # 如果正在调整大小，保持相应的光标
        if self.resize_config.resizing and self.resize_config.resize_direction:
            return

        direction = self.get_resize_direction(pos)

        # 只有当方向改变时才更新光标，减少不必要的设置
        if direction != self.cursor.last_direction:
            cursor_map = {
                'horizontal': Qt.SizeHorCursor,
                'vertical': Qt.SizeVerCursor,
                'b_diagonal': Qt.SizeFDiagCursor,
                'f_diagonal': Qt.SizeBDiagCursor
            }

            new_cursor = cursor_map.get(direction, Qt.ArrowCursor)

            if new_cursor != self.cursor.last_cursor:
                self.setCursor(new_cursor)
                self.cursor.last_cursor = new_cursor
                self.cursor.last_direction = direction
        # 额外检查：如果当前在中部区域但光标不是箭头，则强制设置
        elif direction is None and self.cursor.last_cursor != Qt.ArrowCursor:
            self.setCursor(Qt.ArrowCursor)
            self.cursor.last_cursor = Qt.ArrowCursor
            self.cursor.last_direction = None

    def is_mouse_over_controls(self, pos):
        """检查鼠标是否在任何控制控件上，添加对新按钮的检查"""
        # 将全局坐标转换为控件的局部坐标
        widgets = [
            self.widgets.source_lang_label,
            self.widgets.source_language,
            self.widgets.target_lang_label,
            self.widgets.target_language,
            self.widgets.toggle_button,
            self.widgets.minimize_button,
            self.widgets.maximize_button,
            self.widgets.close_button
        ]

        for widget in widgets:
            # 将窗口坐标转换为控件的局部坐标
            widget_pos = widget.mapFrom(self, pos)
            if widget.rect().contains(widget_pos):
                return True

        return False

    def setup_animation(self):
        """设置边框动画定时器"""
        self.animation.animation_timer = QTimer(self)
        self.animation.animation_timer.timeout.connect(self.update_animation)
        # 初始不启动动画，直到开始翻译
        self.animation.animation_timer.stop()

    def update_animation(self):
        """更新动画进度，确保进度增量计算精确"""
        # 基于定时器间隔和总时长计算精确的进度增量
        progress_increment = (30.0 / self.animation.border_animation_duration) * 100
        self.animation.animation_progress = (
            self.animation.animation_progress + progress_increment) % 100
        self.update()  # 触发窗口重绘
    # pylint: disable=invalid-name
    def paintEvent(self, _event):
        """手动绘制圆角背景和流动边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        self._draw_background(painter)
        self._draw_border(painter)
        self._draw_text(painter)

    def _draw_background(self, painter):
        """绘制背景，确保背景矩形与窗口大小同步"""
        # 基于当前窗口大小计算背景矩形，避免累积误差
        current_rect = self.rect()

        # 清除背景
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(current_rect, Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # 绘制半透明磨砂玻璃效果背景，四个角都设置为圆角
        bg_color = QColor(
            self.theme.dark.red(),
            self.theme.dark.green(),
            self.theme.dark.blue(),
            255
        )
        # 将QRect转换为QRectF以匹配addRoundedRect的参数要求
        rect = QRectF(current_rect.adjusted(1, 1, -1, -1))

        # 使用QPainterPath绘制圆角矩形背景
        self.background.path = QPainterPath()
        self.background.path.addRoundedRect(rect, 10, 10)
        painter.fillPath(self.background.path, QBrush(bg_color))

    def _draw_border(self, painter):
        """绘制边框"""
        # 确保背景矩形已初始化
        if self.background.rect is None:
            self.background.rect = QRectF(self.rect().adjusted(1, 1, -1, -1))

        # 根据动画状态绘制不同边框
        if self.animation.is_animation_active:
            # 动画激活 - 绘制流动边框
            # 创建渐变画笔，实现流动高光效果
            gradient = QConicalGradient()
            gradient.setCenter(self.background.rect.center())

            # 使用动画进度
            angle = (self.animation.animation_progress / 100.0) * -360
            gradient.setAngle(angle)

            # 添加渐变颜色：深蓝 -> 亮蓝 -> 白 -> 亮蓝 -> 深蓝
            gradient.setColorAt(0.0, self.theme.blue.darker(120))
            gradient.setColorAt(0.3, self.theme.blue)
            gradient.setColorAt(0.5, QColor(255, 255, 255))  # 高光
            gradient.setColorAt(0.7, self.theme.blue)
            gradient.setColorAt(1.0, self.theme.blue.darker(120))

            # 创建带渐变的画笔，1px宽度
            border_pen = QPen(QBrush(gradient), 1, Qt.SolidLine)
        else:
            # 动画未激活 - 绘制普通静态边框
            border_pen = QPen(self.theme.blue, 1, Qt.SolidLine)

        painter.setPen(border_pen)
        # 确保路径已初始化
        if self.background.path is None:
            self.background.path = QPainterPath()
            self.background.path.addRoundedRect(self.background.rect, 10, 10)
        # 绘制边框路径（无论是静态还是动态，都需要绘制基础边框）
        painter.drawPath(self.background.path)

    def _draw_text(self, painter):
        """绘制文本内容"""
        # 处理文本内容
        text = self.translator.realtime_text
        lines = text.split('\n', 1)  # 只分割成两部分，确保处理空文本情况
        original_text = lines[0] if len(lines) > 0 else ""
        translated_text = lines[1] if len(lines) > 1 else ""

        # 设置字体及相关参数
        font = self.get_font(12, QFont.Bold)
        painter.setFont(font)
        font_metrics = QFontMetrics(font)

        # 计算文本布局
        wrapped_original = self.wrap_text(original_text, font_metrics, self.width() - 40)
        wrapped_translated = self.wrap_text(translated_text, font_metrics, self.width() - 40)

        # 计算文本区域高度
        has_both_texts = wrapped_original and wrapped_translated
        total_height = (
            (len(wrapped_original) + len(wrapped_translated)) * font_metrics.height() +
            (len(wrapped_original) + len(wrapped_translated) - 1) * 5 +
            (8 if has_both_texts else 0)
        )

        # 计算起始位置并设置描边
        current_y = (self.height() - total_height) // 2 + font_metrics.ascent()
        painter.setPen(QPen(Qt.black, 2))

        # 绘制原文
        current_y = self._draw_text_lines(
            painter, wrapped_original, current_y,
            {"font": font, "gradient_colors": (QColor(220, 230, 255), QColor(255, 255, 255))}
        )

        # 添加间距并绘制译文
        if has_both_texts:
            current_y += 8

        self._draw_text_lines(
            painter, wrapped_translated, current_y,
            {
                "font": font,
                "gradient_colors": (
                    self.theme.blue.lighter(130),
                    self.theme.blue.lighter(180)
                )
            }
        )

    def _draw_text_lines(self, painter, lines, start_y, text_style):
        """绘制多行文本并返回最后一行的Y坐标
        参数:
            painter: 绘图工具
            lines: 待绘制的文本行列表
            start_y: 起始Y坐标
            text_style: 文本样式字典，包含font和gradient_colors
        """
        current_y = start_y
        font = text_style["font"]
        font_metrics = QFontMetrics(font)
        line_height = font_metrics.height()

        for line in lines:
            line_width = font_metrics.width(line)
            line_x = (self.width() - line_width) // 2

            path_text = QPainterPath()
            path_text.addText(line_x, current_y, font, line)

            # 绘制文本描边
            painter.strokePath(path_text, painter.pen())

            # 使用渐变填充文本
            gradient = QLinearGradient(0, 0, 0, line_height)
            gradient.setColorAt(0, text_style["gradient_colors"][0])
            gradient.setColorAt(1, text_style["gradient_colors"][1])
            painter.fillPath(path_text, QBrush(gradient))

            current_y += line_height + 5  # 行间距

        return current_y

    def wrap_text(self, text, font_metrics, max_width):
        """将文本按最大宽度自动换行，改进算法以更好地适应不同分辨率"""
        if not text:  # 处理空文本情况
            return []

        wrapped_lines = []
        current_line = []
        words = text.split(' ')

        for word in words:
            # 检查当前单词是否过长，需要单独拆分
            if font_metrics.width(word) > max_width:
                # 如果当前行有内容，先添加当前行
                if current_line:
                    wrapped_lines.append(' '.join(current_line))
                    current_line = []

                # 拆分过长的单词（按字符拆分）
                current_word = ''
                for char in word:
                    test_word = current_word + char
                    if font_metrics.width(test_word) > max_width:
                        wrapped_lines.append(current_word)
                        current_word = char
                    else:
                        current_word = test_word
                if current_word:
                    current_line.append(current_word)
            else:
                # 普通单词，检查添加后是否超过宽度
                test_line = ' '.join(current_line + [word])
                if font_metrics.width(test_line) <= max_width:
                    current_line.append(word)
                else:
                    # 当前行已满，添加到结果并开始新行
                    wrapped_lines.append(' '.join(current_line))
                    current_line = [word]

        # 添加最后一行
        if current_line:
            wrapped_lines.append(' '.join(current_line))

        return wrapped_lines
    # pylint: disable=invalid-name
    def initUI(self):
        """初始化窗口的方法"""
        # 使用多语言窗口标题
        self.setWindowTitle(INFO.get("window_title", self.language))
        self.setGeometry(106, 654, 1267, 260)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 无标题栏但保留任务栏标签
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # 初始设置为基础透明度（修正属性访问路径）
        self.setWindowOpacity(self.opacity.base_opacity)

        # 创建控制区域布局
        self.create_control_widgets()

        # 添加控制部件到窗口（修正控件属性访问路径）
        self.widgets.control_frame = QFrame(self)
        self.widgets.control_frame.setAttribute(Qt.WA_TranslucentBackground)
        self.widgets.control_frame.setStyleSheet("background-color: transparent;")

        # 修正QHBoxLayout的使用（确保已正确导入）
        self.widgets.control_layout = QHBoxLayout(self.widgets.control_frame)
        self.widgets.control_layout.setContentsMargins(10, 10, 10, 10)
        self.widgets.control_layout.setSpacing(8)

        # 添加控制部件到布局 - 调整顺序，将三个下拉菜单归到一起（修正控件访问路径）
        self.widgets.control_layout.addWidget(self.widgets.source_lang_label)
        self.widgets.control_layout.addWidget(self.widgets.source_language)
        self.widgets.control_layout.addWidget(self.widgets.target_lang_label)
        self.widgets.control_layout.addWidget(self.widgets.target_language)
        self.widgets.control_layout.addWidget(self.widgets.format_label)
        self.widgets.control_layout.addWidget(self.widgets.output_format)
        self.widgets.control_layout.addWidget(self.widgets.convert_button)
        self.widgets.control_layout.addWidget(self.widgets.toggle_button)

        # 添加伸缩项，将最小化、最大化和关闭按钮推到右侧
        self.widgets.control_layout.addStretch()
        self.widgets.control_layout.addWidget(self.widgets.minimize_button)
        self.widgets.control_layout.addWidget(self.widgets.maximize_button)
        self.widgets.control_layout.addWidget(self.widgets.close_button)

        # 设置控制区和字幕区位置和大小（修正控件访问路径）
        self.widgets.control_frame.setGeometry(0, 0, self.width(), 40)

        # 初始化按钮状态
        self.update_button_style(False)

    def create_control_widgets(self):
        """生成控件的方法"""
        self._create_language_controls()
        self._create_translation_button()
        self._create_format_controls()
        self._create_window_controls()

    def _create_language_controls(self):
        """创建语言选择相关控件，优化字体显示和多语言支持"""
        # 源语种标签 - 使用多语言文本
        self.widgets.source_lang_label = QLabel(
            INFO.get("source_lang_label", self.language)
        )
        self.widgets.source_lang_label.setFont(self.get_font(9, QFont.Bold))
        self.widgets.source_lang_label.setStyleSheet("color: white; background-color: transparent;")
        self.widgets.source_lang_label.setAlignment(Qt.AlignVCenter)
        # 添加鼠标事件处理
        self.widgets.source_lang_label.enterEvent = lambda e: self.setCursor(Qt.ArrowCursor)

        # 源语种下拉框（小型）
        self.widgets.source_language = QComboBox()
        # 根据当前语言设置显示对应的语言选项
        lang_options = {
            Config.LANGUAGE_CHINESE: {
                "英语 (en)": "en",
                "俄语 (ru)": "ru",
                "法语 (fr)": "fr",
                "德语 (de)": "de",
                "意语 (it)": "it",
                "日语 (ja)": "ja",
                "韩语 (ko)": "ko",
                "西语 (es)": "es",
                "中文 (zh)": "zh",
                "粤语 (yue)": "yue"
            },
            Config.LANGUAGE_ENGLISH: {
                "English (en)": "en",
                "Russian (ru)": "ru",
                "French (fr)": "fr",
                "German (de)": "de",
                "Italian (it)": "it",
                "Japanese (ja)": "ja",
                "Korean (ko)": "ko",
                "Spanish (es)": "es",
                "Chinese (zh)": "zh",
                "Cantonese (yue)": "yue"
            },
            Config.LANGUAGE_JAPANESE: {
                "英語 (en)": "en",
                "ロシア語 (ru)": "ru",
                "フランス語 (fr)": "fr",
                "ドイツ語 (de)": "de",
                "イタリア語 (it)": "it",
                "日本語 (ja)": "ja",
                "韓国語 (ko)": "ko",
                "スペイン語 (es)": "es",
                "中国語 (zh)": "zh",
                "広東語 (yue)": "yue"
            },
            Config.LANGUAGE_KOREAN: {
                "영어 (en)": "en",
                "러시아어 (ru)": "ru",
                "프랑스어 (fr)": "fr",
                "독일어 (de)": "de",
                "이탈리아어 (it)": "it",
                "일본어 (ja)": "ja",
                "한국어 (ko)": "ko",
                "스페인어 (es)": "es",
                "중국어 (zh)": "zh",
                "광동어 (yue)": "yue"
            }
        }

        # 获取当前语言对应的选项，默认为英语
        self.widgets.lang_map_source = lang_options.get(
            self.language,
            lang_options[Config.LANGUAGE_ENGLISH]
        )
        self.widgets.source_language.addItems(list(self.widgets.lang_map_source.keys()))

        # 设置默认选项
        default_options = {
            Config.LANGUAGE_CHINESE: "英语 (en)",
            Config.LANGUAGE_ENGLISH: "English (en)",
            Config.LANGUAGE_JAPANESE: "英語 (en)",
            Config.LANGUAGE_KOREAN: "영어 (en)"
        }
        default_text = default_options.get(
            self.language,
            default_options[Config.LANGUAGE_ENGLISH]
        )
        self.widgets.source_language.setCurrentText(default_text)

        # 设置字体 - 为下拉框本身和下拉列表分别设置字体
        self.widgets.source_language.setFont(self.get_font(9))
        self.widgets.source_language.setMinimumWidth(90)
        self.widgets.source_language.setMaximumHeight(24)

        # 优化样式表，确保下拉列表使用正确字体
        self.widgets.source_language.setStyleSheet(f"""
            QComboBox {{
                color: white;
                background-color: rgba(
                    {self.theme.gray.red()},
                    {self.theme.gray.green()},
                    {self.theme.gray.blue()},
                    180
                );
                border: 1px solid rgb(
                    {self.theme.blue.red()},
                    {self.theme.blue.green()},
                    {self.theme.blue.blue()}
                );
                border-radius: 4px;
                padding: 2px 3px 2px 5px;
                font-family: {self.get_font().family()};
            }}
            QComboBox:disabled {{
                color: #999999;
                background-color: rgba(
                    {self.theme.gray.red()},
                    {self.theme.gray.green()},
                    {self.theme.gray.blue()},
                    100
                );
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                border-left-width: 1px;
                border-left-color: darkgray;
                border-left-style: solid;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid white;
                margin: 0 3px;
                font-family: Helvetica, sans-serif;
            }}
            QComboBox QAbstractItemView {{
                color: white;
                background-color: rgb(
                    {self.theme.gray.red()},
                    {self.theme.gray.green()},
                    {self.theme.gray.blue()}
                );
                selection-background-color: rgb(
                    {self.theme.blue.red()},
                    {self.theme.blue.green()},
                    {self.theme.blue.blue()}
                );
                border-radius: 4px;
                padding: 2px;
                font-family: {self.get_font().family()};
            }}
        """)
        # 添加鼠标事件处理
        self.widgets.source_language.enterEvent = lambda e: self.setCursor(Qt.ArrowCursor)

        # 目标语种标签 - 使用多语言文本
        self.widgets.target_lang_label = QLabel(INFO.get("target_lang_label", self.language))
        self.widgets.target_lang_label.setFont(self.get_font(9, QFont.Bold))
        self.widgets.target_lang_label.setStyleSheet("color: white; background-color: transparent;")
        self.widgets.target_lang_label.setAlignment(Qt.AlignVCenter)
        # 添加鼠标事件处理
        self.widgets.target_lang_label.enterEvent = lambda e: self.setCursor(Qt.ArrowCursor)

        # 目标语种下拉框（小型）
        self.widgets.target_language = QComboBox()
        # 根据当前语言设置显示对应的目标语言选项
        target_lang_options = {
            Config.LANGUAGE_CHINESE: {
                "中文 (zh)": "zh",
                "英语 (en)": "en",
                "日语 (ja)": "ja",
                "韩语 (ko)": "ko"
            },
            Config.LANGUAGE_ENGLISH: {
                "Chinese (zh)": "zh",
                "English (en)": "en",
                "Japanese (ja)": "ja",
                "Korean (ko)": "ko"
            },
            Config.LANGUAGE_JAPANESE: {
                "中国語 (zh)": "zh",
                "英語 (en)": "en",
                "日本語 (ja)": "ja",
                "韓国語 (ko)": "ko"
            },
            Config.LANGUAGE_KOREAN: {
                "중국어 (zh)": "zh",
                "영어 (en)": "en",
                "일본어 (ja)": "ja",
                "한국어 (ko)": "ko"
            }
        }

        # 获取当前语言对应的目标选项，默认为英语
        self.widgets.lang_map_target = target_lang_options.get(
            self.language,
            target_lang_options[Config.LANGUAGE_ENGLISH]
        )
        self.widgets.target_language.addItems(list(self.widgets.lang_map_target.keys()))

        # 设置默认目标语言
        target_defaults = {
            Config.LANGUAGE_CHINESE: "中文 (zh)",
            Config.LANGUAGE_ENGLISH: "Chinese (zh)",
            Config.LANGUAGE_JAPANESE: "日本語 (ja)",
            Config.LANGUAGE_KOREAN: "한국어 (ko)"
        }
        target_default_text = target_defaults.get(
            self.language,
            target_defaults[Config.LANGUAGE_ENGLISH]
        )
        self.widgets.target_language.setCurrentText(target_default_text)

        # 设置字体和样式
        self.widgets.target_language.setFont(self.get_font(9))
        self.widgets.target_language.setMinimumWidth(90)
        self.widgets.target_language.setMaximumHeight(24)
        self.widgets.target_language.setStyleSheet(self.widgets.source_language.styleSheet())
        # 添加鼠标事件处理
        self.widgets.target_language.enterEvent = lambda e: self.setCursor(Qt.ArrowCursor)

    def _create_translation_button(self):
        """创建翻译按钮相关控件"""
        # 翻译按钮（小型）- 使用多语言文本
        self.widgets.toggle_button = QPushButton(INFO.get("start_button", self.language))
        self.widgets.toggle_button.setFont(self.get_font(9, QFont.Bold))
        self.widgets.toggle_button.setMinimumWidth(50)
        self.widgets.toggle_button.setMaximumHeight(24)
        # 创建按钮渐变背景
        self.update_button_style(False)
        self.widgets.toggle_button.clicked.connect(self.toggle_translation)

        # 添加悬停效果和光标处理
        def on_toggle_enter(_e):
            self.button_hover_effect(True)
            self.setCursor(Qt.ArrowCursor)
        self.widgets.toggle_button.enterEvent = on_toggle_enter
        self.widgets.toggle_button.leaveEvent = lambda e: self.button_hover_effect(False)

    def _create_format_controls(self):
        """创建格式选择相关控件"""
        # 格式选择标签 - 使用多语言文本
        self.widgets.format_label = QLabel(INFO.get("format_label", self.language))
        self.widgets.format_label.setFont(self.get_font(9, QFont.Bold))
        self.widgets.format_label.setStyleSheet("color: white; background-color: transparent;")
        self.widgets.format_label.setAlignment(Qt.AlignVCenter)
        self.widgets.format_label.enterEvent = lambda e: self.setCursor(Qt.ArrowCursor)

        # 格式转换按钮 - 使用多语言文本
        self.widgets.convert_button = QPushButton(INFO.get("convert_button", self.language))
        self.widgets.convert_button.setFont(self.get_font(9, QFont.Bold))
        self.widgets.convert_button.setMinimumWidth(60)
        self.widgets.convert_button.setMaximumHeight(24)
        # 修复绿色渐变背景的语法
        self.widgets.convert_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #27ae60, stop:1 #2ecc71);
                color: white;
                border-radius: 4px;
                padding: 2px;
            }
            QPushButton:disabled {
                background: #999999;
                color: #666666;
            }
        """)

        # 连接result recorder信号
        self.widgets.convert_button.clicked.connect(
            lambda: self.result_recorder.convert_result_format(
                self.widgets.output_format,
                self.widgets.format_options,
                self  # 作为parent传递，用于QMessageBox
            )
        )

        # 为转换按钮添加悬停效果
        def on_convert_enter(_e):
            self.button_hover_effect(True, widget=self.widgets.convert_button)
            self.setCursor(Qt.ArrowCursor)
        self.widgets.convert_button.enterEvent = on_convert_enter
        self.widgets.convert_button.leaveEvent = lambda e: self.button_hover_effect(
            False, widget=self.widgets.convert_button
        )

        # 格式选择下拉框
        self.widgets.output_format = QComboBox()
        # 使用多语言格式选项
        self.widgets.format_options = {
            INFO.get(
                "format_side_by_side",
                self.language
            ): INFO.get(
                "original_translation_parallel",
                self.language
            ),
            INFO.get(
                "format_separated",
                self.language
            ): INFO.get(
                "original_translation_separate",
                self.language
            )
        }
        self.widgets.output_format.addItems(list(self.widgets.format_options.keys()))
        self.widgets.output_format.setCurrentText(
            INFO.get("format_side_by_side", self.language)
        )
        self.widgets.output_format.setFont(self.get_font(9))
        self.widgets.output_format.setMinimumWidth(80)
        self.widgets.output_format.setMaximumHeight(24)
        self.widgets.output_format.setStyleSheet(f"""
            QComboBox {{
                color: white;
                background-color: rgba(
                    {self.theme.gray.red()},
                    {self.theme.gray.green()},
                    {self.theme.gray.blue()},
                    180
                );
                border: 1px solid rgb(
                    {self.theme.blue.red()},
                    {self.theme.blue.green()},
                    {self.theme.blue.blue()}
                );
                border-radius: 4px;
                padding: 2px 3px 2px 5px;
            }}
            QComboBox:disabled {{
                color: #999999;
                background-color: rgba(
                    {self.theme.gray.red()},
                    {self.theme.gray.green()},
                    {self.theme.gray.blue()},
                    100
                );
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                border-left-width: 1px;
                border-left-color: darkgray;
                border-left-style: solid;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid white;
                margin: 0 3px;
            }}
            QComboBox QAbstractItemView {{
                color: white;
                background-color: rgb(
                    {self.theme.gray.red()},
                    {self.theme.gray.green()},
                    {self.theme.gray.blue()}
                );
                selection-background-color: rgb(
                    {self.theme.blue.red()},
                    {self.theme.blue.green()},
                    {self.theme.blue.blue()}
                );
                border-radius: 4px;
                padding: 2px;
            }}
        """)
        self.widgets.output_format.enterEvent = lambda e: self.setCursor(Qt.ArrowCursor)

    def _create_window_controls(self):
        """创建窗口控制按钮（最小化、最大化、关闭）"""
        # 最小化按钮
        self.widgets.minimize_button = QPushButton("−")
        # 强制使用Helvetica字体显示符号
        font = QFont("Helvetica", 8, QFont.Bold)
        self.widgets.minimize_button.setFont(font)
        self.widgets.minimize_button.setFixedSize(24, 24)
        # 简化样式表，避免解析问题
        self.widgets.minimize_button.setStyleSheet(f"""
            QPushButton {{
                color: white;
                background-color: rgba({self.theme.gray.red()},
                                     {self.theme.gray.green()},
                                     {self.theme.gray.blue()}, 150);
                border-radius: 12px;
                padding: 0px;
                border: none;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: rgb({self.theme.light_blue.red()},
                                      {self.theme.light_blue.green()},
                                      {self.theme.light_blue.blue()});
            }}
            QPushButton::menu-indicator {{
                image: none;
            }}
        """)
        self.widgets.minimize_button.clicked.connect(self.showMinimized)

        # 最大化/还原按钮
        self.widgets.maximize_button = QPushButton("□")
        self.widgets.maximize_button.setFont(font)
        self.widgets.maximize_button.setFixedSize(24, 24)
        # 简化样式表
        self.widgets.maximize_button.setStyleSheet(f"""
            QPushButton {{
                color: white;
                background-color: rgba({self.theme.gray.red()},
                                     {self.theme.gray.green()},
                                     {self.theme.gray.blue()}, 150);
                border-radius: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: rgb({self.theme.light_blue.red()},
                                     {self.theme.light_blue.green()},
                                     {self.theme.light_blue.blue()});
            }}
        """)
        self.widgets.maximize_button.clicked.connect(self.toggle_maximize)

        # 关闭按钮（右上角）
        self.widgets.close_button = QPushButton("×")
        self.widgets.close_button.setFont(font)
        self.widgets.close_button.setFixedSize(24, 24)
        # 简化样式表
        self.widgets.close_button.setStyleSheet(f"""
            QPushButton {{
                color: white;
                background-color: rgba({self.theme.gray.red()},
                                     {self.theme.gray.green()},
                                     {self.theme.gray.blue()}, 150);
                border-radius: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: #e74c3c;
            }}
        """)
        self.widgets.close_button.clicked.connect(self.close)

        # 为关闭按钮添加透明度变化效果和光标处理
        def on_close_enter(_e):
            self.setCursor(Qt.ArrowCursor)
        self.widgets.close_button.enterEvent = on_close_enter
        self.widgets.close_button.leaveEvent = lambda e: None

    def update_button_style(self, is_running):
        """更新按钮样式的方法"""
        if is_running:
            # 停止状态 - 红色
            self.widgets.toggle_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #e74c3c, stop:1 #c0392b);
                    color: white;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
        else:
            # 开始状态 - 蓝色，修复渐变语法
            self.widgets.toggle_button.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgb({self.theme.blue.red()},
                                  {self.theme.blue.green()},
                                  {self.theme.blue.blue()}),
                        stop:1 rgb({self.theme.light_blue.red()},
                                  {self.theme.light_blue.green()},
                                  {self.theme.light_blue.blue()}));
                    color: white;
                    border-radius: 4px;
                    padding: 2px;
                }}
            """)

    def button_hover_effect(self, is_hovered, widget=None):
        """修改按钮悬停效果方法，支持指定按钮"""

        # 如果未指定按钮，默认使用toggle_button
        target_button = widget if widget else self.widgets.toggle_button

        if is_hovered:
            # 按钮放大动画
            animation = QPropertyAnimation(target_button, b"geometry")
            animation.setDuration(200)
            animation.setEasingCurve(QEasingCurve.InOutQuad)
            current_geo = target_button.geometry()
            animation.setStartValue(current_geo)
            animation.setEndValue(QRect(
                current_geo.x() - 1,
                current_geo.y() - 1,
                current_geo.width() + 2,
                current_geo.height() + 2
            ))
            animation.start()
        else:
            # 按钮恢复原大小
            animation = QPropertyAnimation(target_button, b"geometry")
            animation.setDuration(200)
            animation.setEasingCurve(QEasingCurve.InOutQuad)
            current_geo = target_button.geometry()
            animation.setStartValue(current_geo)
            animation.setEndValue(QRect(
                current_geo.x() + 1,
                current_geo.y() + 1,
                current_geo.width() - 2,
                current_geo.height() - 2
            ))
            animation.start()

    # pylint: disable=invalid-name
    def mousePressEvent(self, event):
        """处理鼠标点击的方法"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()

            # 如果点击在控件上，使用默认处理
            if self.is_mouse_over_controls(pos):
                # 确保事件被控件接收
                event.ignore()
                return

            # 检查是否应该调整窗口大小
            self.resize_config.resize_direction = self.get_resize_direction(pos)

            if self.resize_config.resize_direction:
                self.resize_config.resizing = True
                self.window.original_rect = self.geometry()
                self.window.original_pos = event.globalPos()
                # 设置对应的调整光标
                self.set_cursor_based_on_position(pos)
            else:
                # 否则进行窗口拖动
                self.drag.dragging = True
                self.drag.offset = event.globalPos() - self.pos()
                # 拖动时使用移动光标
                self.setCursor(Qt.SizeAllCursor)
    # pylint: disable=invalid-name
    def mouseMoveEvent(self, event):
        """处理鼠标移动的方法"""
        try:
            # 无论是否在调整大小或拖动，都先更新位置信息
            current_pos = event.pos()
            if self.resize_config.resizing and self.resize_config.resize_direction:
                self._handle_resizing(event, current_pos)
            elif self.drag.dragging:
                self._handle_dragging(event)
            else:
                # 强制更新光标，使用阻塞方式确保立即生效
                self.set_cursor_based_on_position(current_pos)
                # 立即刷新以确保光标状态更新
                QApplication.processEvents()

            # 鼠标移动重置闲置计时器
            self.timers.idle_timer.start(self.timers.idle_delay)

        except (AttributeError, TypeError, ValueError) as e:
            print(INFO.get("mouse_move_event_error", self.language).format(error=str(e)))

    def _handle_resizing(self, event, _current_pos):
        """处理窗口大小调整"""
        global_pos = event.globalPos()
        current_geo = self.geometry()
        orig_rect = self.window.original_rect
        orig_pos = self.window.original_pos

        resize_methods = {
            'horizontal': self._handle_horizontal_resize,
            'vertical': self._handle_vertical_resize,
            'b_diagonal': self._handle_b_diagonal_resize,
            'f_diagonal': self._handle_f_diagonal_resize
        }

        if self.resize_config.resize_direction in resize_methods:
            current_geo = resize_methods[self.resize_config.resize_direction](
                global_pos, orig_rect, orig_pos, current_geo
            )
            self.setGeometry(current_geo)
            # 更新控制区域大小
            self.widgets.control_frame.setGeometry(0, 0, self.width(), 40)

    def _handle_horizontal_resize(self, global_pos, orig_rect, orig_pos, current_geo):
        """处理水平方向调整"""
        delta_x = global_pos.x() - orig_pos.x()
        orig_x, orig_width = orig_rect.x(), orig_rect.width()

        # 左侧调整
        if orig_pos.x() <= orig_x + self.resize_config.border_width:
            new_x = orig_x + delta_x
            new_width = orig_width - delta_x
            if new_width >= self.resize_config.min_width:
                current_geo.setX(new_x)
                current_geo.setWidth(new_width)
        # 右侧调整
        else:
            new_width = orig_width + delta_x
            if new_width >= self.resize_config.min_width:
                current_geo.setWidth(new_width)
        return current_geo

    def _handle_vertical_resize(self, global_pos, orig_rect, orig_pos, current_geo):
        """处理垂直方向调整"""
        delta_y = global_pos.y() - orig_pos.y()
        orig_y, orig_height = orig_rect.y(), orig_rect.height()

        # 顶部调整
        if orig_pos.y() <= orig_y + self.resize_config.border_width:
            new_y = orig_y + delta_y
            new_height = orig_height - delta_y
            if new_height >= self.resize_config.min_height:
                current_geo.setY(new_y)
                current_geo.setHeight(new_height)
        # 底部调整
        else:
            new_height = orig_height + delta_y
            if new_height >= self.resize_config.min_height:
                current_geo.setHeight(new_height)
        return current_geo

    def _handle_b_diagonal_resize(self, global_pos, orig_rect, orig_pos, current_geo):
        """处理B对角线方向调整 (左上-右下)"""
        delta_x = global_pos.x() - orig_pos.x()
        delta_y = global_pos.y() - orig_pos.y()
        orig_x, orig_y = orig_rect.x(), orig_rect.y()
        orig_width, orig_height = orig_rect.width(), orig_rect.height()

        # 左上调整
        if (orig_pos.x() <= orig_x + self.resize_config.border_width and
                orig_pos.y() <= orig_y + self.resize_config.border_width):
            new_x = orig_x + delta_x
            new_y = orig_y + delta_y
            new_width = orig_width - delta_x
            new_height = orig_height - delta_y

            if (new_width >= self.resize_config.min_width and
                new_height >= self.resize_config.min_height):
                current_geo.setX(new_x)
                current_geo.setY(new_y)
                current_geo.setWidth(new_width)
                current_geo.setHeight(new_height)
        # 右下调整
        else:
            new_width = orig_width + delta_x
            new_height = orig_height + delta_y

            if (new_width >= self.resize_config.min_width and
                new_height >= self.resize_config.min_height):
                current_geo.setWidth(new_width)
                current_geo.setHeight(new_height)
        return current_geo

    def _handle_f_diagonal_resize(self, global_pos, orig_rect, orig_pos, current_geo):
        """处理F对角线方向调整 (右上-左下)"""
        delta_x = global_pos.x() - orig_pos.x()
        delta_y = global_pos.y() - orig_pos.y()
        orig_x, orig_y = orig_rect.x(), orig_rect.y()
        orig_width, orig_height = orig_rect.width(), orig_rect.height()

        # 右上调整
        if (orig_pos.x() >= orig_x + orig_width - self.resize_config.border_width and
                orig_pos.y() <= orig_y + self.resize_config.border_width):
            new_width = orig_width + delta_x
            new_y = orig_y + delta_y
            new_height = orig_height - delta_y

            if (new_width >= self.resize_config.min_width and
                new_height >= self.resize_config.min_height):
                current_geo.setY(new_y)
                current_geo.setWidth(new_width)
                current_geo.setHeight(new_height)
        # 左下调整
        else:
            new_x = orig_x + delta_x
            new_width = orig_width - delta_x
            new_height = orig_height + delta_y

            if (new_width >= self.resize_config.min_width and
                new_height >= self.resize_config.min_height):
                current_geo.setX(new_x)
                current_geo.setWidth(new_width)
                current_geo.setHeight(new_height)
        return current_geo

    def _handle_dragging(self, event):
        """处理窗口拖动"""
        new_pos = event.globalPos() - self.drag.offset

        # 如果窗口处于最大化状态，锁定x坐标（左右不移动）
        if self.window.is_maximized:
            # 保持x坐标为0（全屏宽度），只改变y坐标
            new_pos.setX(0)

        self.move(new_pos)

    # pylint: disable=invalid-name
    def mouseReleaseEvent(self, event):
        """处理鼠标释放的方法"""
        if event.button() == Qt.LeftButton:
            # 保存当前鼠标位置用于后续光标设置
            current_pos = event.pos()

            # 停止调整大小或拖动
            self.resize_config.resizing = False
            self.drag.dragging = False

            # 释放鼠标时根据当前位置更新光标
            self.set_cursor_based_on_position(current_pos)

            # 额外检查：如果释放位置在中间区域，强制设置为箭头
            if (self.resize_config.border_width < current_pos.x() <
                    self.width() - self.resize_config.border_width and
                    self.resize_config.border_width < current_pos.y() <
                    self.height() - self.resize_config.border_width):
                self.setCursor(Qt.ArrowCursor)
                self.cursor.last_cursor = Qt.ArrowCursor
                self.cursor.last_direction = None

    def enterEvent(self, event):
        """处理鼠标进入的方法"""
        try:
            # 鼠标进入时立即更新光标
            current_pos = event.pos()
            self.set_cursor_based_on_position(current_pos)
            # 鼠标进入窗口时
            if self.translator.is_running:
                # 翻译中状态，保持高透明度
                new_opacity = self.opacity.translating_opacity
            else:
                # 非翻译状态，提高透明度
                new_opacity = self.opacity.hover_opacity

            # 统一设置窗口和控制区透明度
            self.setWindowOpacity(new_opacity)
            super().enterEvent(event)
        except (AttributeError, TypeError, RuntimeError) as e:
            print(INFO.get("mouse_enter_event_error", self.language).format(error=str(e)))

    # pylint: disable=invalid-name
    def leaveEvent(self, event):
        """处理鼠标离开的方法"""
        try:
            # 鼠标离开时重置光标状态跟踪
            if self.cursor.last_cursor != Qt.ArrowCursor:
                self.setCursor(Qt.ArrowCursor)
                self.cursor.last_cursor = Qt.ArrowCursor
                self.cursor.last_direction = None

            # 鼠标离开窗口时
            if self.translator.is_running:
                # 翻译中状态，保持高透明度，不启动闲置计时器
                new_opacity = self.opacity.translating_opacity
            else:
                # 非翻译状态，恢复透明度并启动闲置计时器
                new_opacity = self.opacity.base_opacity

            # 统一设置窗口和控制区透明度
            self.setWindowOpacity(new_opacity)

            super().leaveEvent(event)
        except (AttributeError, TypeError) as e:
            print(INFO.get("mouse_leave_event_error", self.language).format(error=str(e)))

    def _on_translator_started(self, success, data):
        """翻译器启动线程完成后的回调方法"""
        if success:
            # 翻译器启动成功，保存实例引用
            self.translator.translator_app = data
        else:
            # 翻译器启动失败，恢复UI状态
            self.translator.is_running = False
            self.widgets.toggle_button.setText(INFO.get("start_button", self.language))
            self.update_button_style(False)
            # 停止动画
            self.animation.animation_timer.stop()
            self.animation.is_animation_active = False
            # 恢复透明度
            self.setWindowOpacity(self.opacity.base_opacity)
            # 启用语言选择和格式相关下拉菜单及按钮
            self.widgets.source_language.setEnabled(True)
            self.widgets.target_language.setEnabled(True)
            self.widgets.output_format.setEnabled(True)
            self.widgets.convert_button.setEnabled(True)
            self.update()

            # 错误已在线程中记录，这里不再重复记录
            # 如需显示用户界面错误提示，可在此处添加

    def toggle_translation(self):  # pylint: disable=too-many-statements
        """处理翻译按钮互动的方法"""
        if not self.translator.is_running:
            # 先更新UI状态，给用户即时反馈
            self.translator.is_running = True
            self.widgets.toggle_button.setText(INFO.get("stop_button", self.language))
            self.update_button_style(True)
            # 开始动画
            self.animation.animation_timer.start(30)
            self.animation.is_animation_active = True
            # 设置固定透明度
            self.setWindowOpacity(self.opacity.translating_opacity)
            # 禁用语言选择和格式相关下拉菜单及按钮
            self.widgets.source_language.setEnabled(False)
            self.widgets.target_language.setEnabled(False)
            self.widgets.output_format.setEnabled(False)
            self.widgets.convert_button.setEnabled(False)
            self.update()

            # 在单独的线程中创建并启动翻译器
            class TranslatorStartThread(QThread):  # pylint: disable=too-few-public-methods
                """用于启动翻译器的线程"""
                started = pyqtSignal(bool, object)

                def __init__(self, ui_instance, source_lang_text, target_lang_text, output_format):
                    super().__init__()
                    self.ui_instance = ui_instance
                    self.source_lang_text = source_lang_text
                    self.target_lang_text = target_lang_text
                    self.output_format = output_format

                def run(self):
                    """在线程中执行翻译器启动操作"""
                    try:
                        # 更新配置
                        # 获取映射值
                        # 获取映射值
                        source_map = self.ui_instance.widgets.lang_map_source
                        target_map = self.ui_instance.widgets.lang_map_target
                        source_map_value = source_map[self.source_lang_text]
                        target_map_value = target_map[self.target_lang_text]

                        # 设置配置
                        Config.ASR_LANGUAGE = source_map_value
                        Config.TRANSLATE_SOURCE = source_map_value
                        Config.TRANSLATE_TARGET = target_map_value

                        # 创建并启动翻译应用，传入格式选择
                        # 创建翻译应用
                        translator_app = TranslatorUnit(
                            Config, self.ui_instance, self.output_format
                        )
                        translator_app.start()

                        # 返回成功结果
                        self.started.emit(True, translator_app)
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        error_msg = f"启动翻译器失败: {str(e)}"
                        self.ui_instance.logger.error(error_msg)
                        self.started.emit(False, error_msg)

            # 获取选中的语种和格式
            source_lang_text = self.widgets.source_language.currentText()
            target_lang_text = self.widgets.target_language.currentText()
            format_text = self.widgets.output_format.currentText()
            output_format = self.widgets.format_options[format_text]

            # 创建并启动线程
            # 创建并启动线程
            self._translation_thread = TranslatorStartThread(
                self, source_lang_text, target_lang_text, output_format
            )  # pylint: disable=attribute-defined-outside-init
            self._translation_thread.started.connect(self._on_translator_started)
            self._translation_thread.start()
        else:
            # 停止翻译
            if self.translator.translator_app:
                try:
                    # 先检查翻译器是否还在运行
                    if (hasattr(self.translator.translator_app, 'thread_state') and
                        not self.translator.translator_app.thread_state.is_running):
                        self.logger.warning(INFO.get(
                            "stop_non_running_translator",
                            self.language
                        ))
                    else:
                        self.translator.translator_app.stop()
                except (RuntimeError, AttributeError) as e:
                    error_msg = INFO.get("error_stopping_translator", self.language)
                    self.logger.error(error_msg.format(error=str(e)))
                finally:
                    self.translator.translator_app = None

            # 更新UI状态
            self.translator.is_running = False
            self.widgets.toggle_button.setText(INFO.get("start_button", self.language))
            self.update_button_style(False)
            # 停止动画
            self.animation.animation_timer.stop()
            self.animation.is_animation_active = False
            # 恢复透明度
            new_opacity = (self.opacity.hover_opacity
                if self.underMouse()
                else self.opacity.base_opacity)
            self.setWindowOpacity(new_opacity)
            # 启用语言选择和格式相关下拉菜单及按钮
            self.widgets.source_language.setEnabled(True)
            self.widgets.target_language.setEnabled(True)
            self.widgets.output_format.setEnabled(True)
            self.widgets.convert_button.setEnabled(True)
            self.update()

    def toggle_maximize(self):
        """切换窗口最大化/还原状态"""
        if not self.window.is_maximized:
            # 保存当前窗口状态
            self.window.normal_geometry = self.geometry()

            # 获取屏幕分辨率
            screen_geometry = QApplication.desktop().availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()

            # 计算新窗口大小：宽度为屏幕宽度，高度为屏幕高度的1/3并减少50px
            new_width = screen_width
            new_height = (screen_height // 3) - 50  # 高度减少50px

            # 计算新窗口位置：紧贴屏幕下沿再上移50px
            new_x = 0
            new_y = screen_height - new_height - 50  # 位置上移50px

            # 应用新的窗口大小和位置
            self.setGeometry(new_x, new_y, new_width, new_height)

            # 更新状态和按钮
            self.window.is_maximized = True
            self.widgets.maximize_button.setText("⧉")
        else:
            # 还原窗口到之前的状态
            if self.window.normal_geometry:
                self.setGeometry(self.window.normal_geometry)

            # 更新状态和按钮
            self.window.is_maximized = False
            self.widgets.maximize_button.setText("□")

        # 调整中间区域
        self.adjust_middle_area()

    def enter_idle_state(self):
        """进入闲置状态，降低透明度（仅在非翻译状态生效）"""
        self.setWindowOpacity(self.opacity.idle_opacity)

    def update_subtitle(self, original, translated=None):
        """
        更新实时文本内容

        支持两种调用方式:
        1. 分别传入原始文本和翻译文本（自动合并）
        2. 仅传入已合并的文本（translated参数留空）
        """
        # 处理仅传入合并文本的情况
        if translated is None:
            combined_text = original
        else:
            # 处理分别传入原始文本和翻译文本的情况
            combined_text = f"{original}\n{translated}"

        # 更新UI显示 - 修复AttributeError，直接更新当前窗口的文本
        self.translator.realtime_text = combined_text
        self.update()  # 触发重绘

    # pylint: disable=invalid-name
    def closeEvent(self, event):
        """
        重写窗口关闭事件，确保优雅退出
        """
        # 停止翻译线程，添加空值检查
        if (hasattr(self, 'translator') and self.translator and
            hasattr(self.translator, 'is_running') and self.translator.is_running):
            if hasattr(self.translator, 'translator_app') and self.translator.translator_app:
                self.translator.translator_app.stop()

        # 停止动画定时器，添加空值检查
        if (hasattr(self, 'animation') and self.animation and
            hasattr(self.animation, 'animation_timer') and self.animation.animation_timer):
            self.animation.animation_timer.stop()

        # 终止整个应用程序进程，添加安全检查
        try:
            app = QApplication.instance()
            if app:
                app.quit()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        event.accept()

    def get_font(self, size=9, weight=QFont.Normal):
        """根据当前语言获取对应的字体
        Args:
            size: 字体大小
            weight: 字体粗细，默认为正常
        Returns:
            QFont对象
        """
        # 创建语言到字体族的映射
        font_families = {
            Config.LANGUAGE_CHINESE: "Microsoft YaHei, SimHei, Heiti TC",
            Config.LANGUAGE_JAPANESE: "MS Gothic, Meiryo, sans-serif",
            Config.LANGUAGE_KOREAN: "Malgun Gothic, Dotum, sans-serif",
            Config.LANGUAGE_ENGLISH: "Segoe UI, Helvetica, sans-serif"
        }

        # 获取当前语言对应的字体族，默认为英文字体
        font_family = font_families.get(self.language, font_families[Config.LANGUAGE_ENGLISH])
        font = QFont(font_family, size, weight)
        return font
