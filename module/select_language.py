"""
语言选择模块
负责程序首次启动时用户选择程序界面及提示通知所使用的语种
"""
from PyQt5 import QtWidgets, QtGui, QtCore
from .config import Config
# pylint: disable=c-extension-no-member
class LanguageSelectionDialog(QtWidgets.QDialog):
    """初始选择界面与提示语言的类"""
    def __init__(self, parent=None):
        """初始化部分"""
        super().__init__(parent)
        # 优化窗口标题和尺寸
        self.setWindowTitle("Select Language")
        self.setMinimumSize(400, 250)  # 减小窗口最小尺寸
        self.selected_language = Config.LANGUAGE_CHINESE

        # 设置字体
        self._setup_font()

        # 创建布局
        self._setup_ui()

    def _setup_font(self):
        """设置统一的字体，确保所有语言界面下的中文字符显示一致"""
        # 统一使用中文字体族，确保中文显示效果一致
        # 优先使用Microsoft YaHei（微软雅黑），这是Windows系统下显示中文的最佳字体
        # 备选字体包括其他常见中文字体，确保跨平台兼容性
        unified_font_family = (
            "Microsoft YaHei, SimHei, Heiti TC, SimSun, NSimSun, "
            "Arial Unicode MS, sans-serif"
        )
        font = QtGui.QFont(unified_font_family, 9)
        self.setFont(font)

    def _setup_ui(self):
        """设置用户界面"""
        # 主布局优化：减小边距和间距
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(15, 15, 15, 15)  # 减少边距
        layout.setSpacing(10)  # 缩小控件间距

        # 提示文本优化：保持自动换行
        prompt_text = (
            "请选择界面语言 "
            "/ Please select interface language "
            "/ インターフェース言語を選択してください "
            "/ 인터페이스 언어를 선택하세요")
        prompt_label = QtWidgets.QLabel(prompt_text)
        prompt_label.setAlignment(QtCore.Qt.AlignCenter)
        prompt_label.setWordWrap(True)
        layout.addWidget(prompt_label)

        # 语言选择按钮：紧凑排列
        self.zh_radio = QtWidgets.QRadioButton("中文")
        self.en_radio = QtWidgets.QRadioButton("English")
        self.ja_radio = QtWidgets.QRadioButton("日本語")
        self.ko_radio = QtWidgets.QRadioButton("한국어")
        self.zh_radio.setChecked(True)

        # 单选按钮样式：减少上下边距
        for radio in [self.zh_radio, self.en_radio, self.ja_radio, self.ko_radio]:
            radio.setStyleSheet("QRadioButton { margin: 3px 0px; }")

        # 信号连接保持不变
        self.zh_radio.toggled.connect(lambda checked: self.on_language_selected(
                                     Config.LANGUAGE_CHINESE, checked))
        self.en_radio.toggled.connect(lambda checked: self.on_language_selected(
                                     Config.LANGUAGE_ENGLISH, checked))
        self.ja_radio.toggled.connect(lambda checked: self.on_language_selected(
                                     Config.LANGUAGE_JAPANESE, checked))
        self.ko_radio.toggled.connect(lambda checked: self.on_language_selected(
                                     Config.LANGUAGE_KOREAN, checked))

        # 单选按钮布局：更紧凑的排列
        radio_layout = QtWidgets.QVBoxLayout()
        radio_layout.setAlignment(QtCore.Qt.AlignCenter)
        radio_layout.setSpacing(5)  # 缩小按钮间距离
        radio_layout.addWidget(self.zh_radio)
        radio_layout.addWidget(self.en_radio)
        radio_layout.addWidget(self.ja_radio)
        radio_layout.addWidget(self.ko_radio)
        layout.addLayout(radio_layout)

        # 确认按钮：减小高度并优化位置
        btn_layout = QtWidgets.QHBoxLayout()
        self.confirm_btn = QtWidgets.QPushButton("确认 / Confirm / 確認 / 확인")
        self.confirm_btn.setMinimumHeight(28)  # 适当减小按钮高度
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 设置主布局
        self.setLayout(layout)

    def on_language_selected(self, language, checked):
        """选择语言"""
        if checked:
            self.selected_language = language

    def get_selected_language(self):
        """获取选择的语种"""
        return self.selected_language
