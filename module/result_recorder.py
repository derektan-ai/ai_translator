"""
结果记录器模块
该模块提供ResultRecorder类，用于处理翻译结果的记录与管理，
支持原译对照和原译分开两种输出格式，并提供结果文件格式转换功能。
"""
import os
import re
import time
from dataclasses import dataclass
from .message_center import message_center
from .config import Config

@dataclass
class LanguageLabels:
    """多语言标签数据类，集中管理所有需要翻译的文本标签"""
    # pylint: disable=R0902
    original_text_label: str
    translated_text_label: str
    all_originals_label: str
    all_translations_label: str
    original_translation_parallel: str
    original_translation_separate: str
    prompt: str
    no_result_folder: str
    no_result_files: str
    success: str
    file_converted: str
    error: str
    file_conversion_failed: str
    error_converting_file: str
    error_occurred: str
    no_valid_translations: str
    translation_complete: str          # 新增：翻译完成
    translation_saved_to: str          # 新增：翻译结果已保存到
    generated_file: str                # 新增：已生成
    no_translation_result: str        # 新增：没有翻译结果可保存
    no_result_generated: str           # 新增：未生成翻译结果文件
    rename_limit_reached: str          # 新增：重命名次数达到上限
    source_language_label: str         # 新增：源语种
    target_language_label: str         # 新增：目标语种

# 预定义支持的语言标签实例
LANGUAGE_LABELS = {
    'zh': LanguageLabels(
        original_text_label='原文',
        translated_text_label='译文',
        all_originals_label='【所有原文】',
        all_translations_label='【所有译文】',
        original_translation_parallel='原译对照',
        original_translation_separate='原译分开',
        prompt='提示',
        no_result_folder='结果文件夹不存在',
        no_result_files='没有找到翻译结果文件',
        success='成功',
        file_converted='文件已转换为{format}格式',
        error='错误',
        file_conversion_failed='文件转换失败',
        error_converting_file='转换文件：',
        error_occurred='时出错',
        no_valid_translations='没有找到有效的翻译内容',
        translation_complete='翻译完成',
        translation_saved_to='翻译结果已保存到',
        generated_file='已生成',
        no_translation_result='没有翻译结果可保存',
        no_result_generated='未生成翻译结果文件',
        rename_limit_reached='重命名次数达到上限',
        source_language_label='源语种',
        target_language_label='目标语种'
    ),
    'en': LanguageLabels(
        original_text_label='Original',
        translated_text_label='Translation',
        all_originals_label='【All Originals】',
        all_translations_label='【All Translations】',
        original_translation_parallel='Original-Translation Parallel',
        original_translation_separate='Original-Translation Separate',
        prompt='Info',
        no_result_folder='result folder does not exist',
        no_result_files='No translation result files found',
        success='Success',
        file_converted='File converted to {format} format successfully',
        error='Error',
        file_conversion_failed='File conversion failed',
        error_converting_file='Error converting file:',
        error_occurred=', error occurred',
        no_valid_translations='No valid translation content found',
        translation_complete='Translation complete',
        translation_saved_to='Translation result saved to',
        generated_file='generated',
        no_translation_result='No translation result to save',
        no_result_generated='No translation result file generated',
        rename_limit_reached='Rename limit reached',
        source_language_label='Source language',
        target_language_label='Target language'
    ),
    'ja': LanguageLabels(
        original_text_label='原文',
        translated_text_label='訳文',
        all_originals_label='【すべての原文】',
        all_translations_label='【すべての訳文】',
        original_translation_parallel='原語と訳語を対照表示',
        original_translation_separate='原語と訳語を分ける',
        prompt='プロンプト',
        no_result_folder='結果フォルダーが存在しません',
        no_result_files='翻訳結果ファイルが見つかりません',
        success='成功',
        file_converted='ファイルが{format}形式に変換されました',
        error='エラー',
        file_conversion_failed='ファイルの変換に失敗しました',
        error_converting_file='ファイル ',
        error_occurred=' の変換時にエラーが発生しました',
        no_valid_translations='有効な翻訳内容が見つかりませんでした',
        translation_complete='翻訳完了',
        translation_saved_to='翻訳結果が保存されました',
        generated_file='生成済み',
        no_translation_result='保存する翻訳結果がありません',
        no_result_generated='翻訳結果ファイルが生成されていません',
        rename_limit_reached='名前変更の上限に達しました',
        source_language_label='原語',
        target_language_label='対象言語'
    ),
    'ko': LanguageLabels(
        original_text_label='원문',
        translated_text_label='번역문',
        all_originals_label='【모든 원문】',
        all_translations_label='【모든 번역문】',
        original_translation_parallel='원문과 번역문 대조',
        original_translation_separate='원문과 번역문 분리',
        prompt='提示',
        no_result_folder='결과 폴더가 존재하지 않습니다',
        no_result_files='번역 결과 파일을 찾을 수 없습니다',
        success='성공',
        file_converted='파일이 {format} 형식으로 변환되었습니다',
        error='오류',
        file_conversion_failed='파일 변환 실패',
        error_converting_file='파일 ',
        error_occurred=' 변환 중 오류 발생',
        no_valid_translations='유효한 번역 내용을 찾을 수 없습니다',
        translation_complete='번역 완료',
        translation_saved_to='번역 결과가 다음 위치에 저장되었습니다',
        generated_file='생성됨',
        no_translation_result='저장할 번역 결과가 없습니다',
        no_result_generated='번역 결과 파일이 생성되지 않았습니다',
        rename_limit_reached='이름 변경 횟수 제한에 도달했습니다',
        source_language_label='원본 언어',
        target_language_label='대상 언어'
    )
}
# pylint: disable=c-extension-no-member
class ResultRecorder:
    """
    结果记录器类，负责将翻译结果记录到文件中
    """
    # pylint: disable=R0902
    def __init__(self, source_lang, target_lang, logger=None, format_config=None):
        """初始化翻译结果处理器"""
        # 从配置获取界面语言
        self.language = Config.LANGUAGE

        # 处理格式配置，设置默认值
        format_config = format_config or {}
        default_format = self._get_label('original_translation_parallel')
        self.output_format = format_config.get('output_format', default_format)
        # 修复：使用正确的变量名，从format_config获取或设置默认值
        self.format_options = format_config.get('format_options', {
            self._get_label('original_translation_parallel'):
                self._get_label('original_translation_parallel'),
            self._get_label('original_translation_separate'):
                self._get_label('original_translation_separate')
        })

        self.source_lang = source_lang
        self.target_lang = target_lang
        self.logger = logger
        self.file_path = self._create_result_file()
        # 标记文件是否已经初始化，延迟到实际需要写入时再创建文件
        self.file_initialized = False
        self.all_originals = []
        self.all_translations = []

    def get_file_path(self):
        """获取结果文件路径"""
        return self.file_path

    def record_translation(self, original_text, translated_text):
        """实时记录单个翻译结果到文件，支持两种格式"""
        if not original_text or not translated_text:
            return False

        # 清理文本
        clean_original = original_text.strip().replace('\n', ' ')
        clean_translated = translated_text.strip().replace('\n', ' ')

        # 保存到内存，用于格式转换
        self.all_originals.append(clean_original)
        self.all_translations.append(clean_translated)

        # 延迟初始化文件，只在第一次写入内容时创建文件并写入头部
        if not self.file_initialized:
            self._write_header()
            self.file_initialized = True

        # 根据格式写入文件
        with open(self.file_path, 'r+', encoding='utf-8') as f:
            if self.output_format == self._get_label('original_translation_parallel'):
                # 移动到文件末尾
                f.seek(0, os.SEEK_END)
                f.write(f"{self._get_label('original_text_label')}: {clean_original}\n")
                f.write(f"{self._get_label('translated_text_label')}: {clean_translated}\n\n")
            else:  # 原译分开
                # 优化：只重新生成内容，避免重复读取整个文件
                f.seek(0)
                header = f.read()
                header_end = header.find("=" * 50) + len("=" * 50) + 1

                # 构建新的内容
                new_content = header[:header_end] + "\n"
                new_content += f"{self._get_label('all_originals_label')}\n"
                new_content += "\n".join(self.all_originals) + "\n"
                new_content += f"\n{self._get_label('all_translations_label')}\n"
                new_content += "\n".join(self.all_translations) + "\n"

                # 写入新内容前再次验证数据有效性
                if not self.all_originals or not self.all_translations:
                    return False

                # 写入新内容
                f.seek(0)
                f.truncate()
                f.write(new_content)

        return True

    def _create_result_file(self):
        """创建结果文件，确保目录存在并生成唯一文件名"""
        # 确保结果目录存在
        os.makedirs(Config.RESULT_DIR, exist_ok=True)

        # 创建基础结果文件名
        base_filename = f"translate_result_{Config.START_TIMESTAMP}"
        base_path = os.path.join(Config.RESULT_DIR, base_filename)
        result_file = f"{base_path}.txt"

        # 检查文件是否已存在，如果存在则添加序号
        counter = 1
        while os.path.exists(result_file):
            result_file = f"{base_path}({counter}).txt"
            counter += 1
            if counter > 999:
                raise RuntimeError(self._get_label('rename_limit_reached'))

        return result_file

    def _write_header(self):
        """写入文件头部信息，包含当前使用的格式"""
        try:
            # 使用更安全的方式检查文件是否存在并写入头部，避免多线程或多实例重复创建
            if not os.path.exists(self.file_path):
                # 尝试创建文件并写入头部
                # 使用os.makedirs确保目录存在
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                # 使用with语句自动处理文件关闭
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    # 改进：头部显示当前使用的格式
                    f.write(f"{self.output_format} - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(
                        f"{self._get_label('source_language_label')}: {self.source_lang} -> "
                        f"{self._get_label('target_language_label')}: {self.target_lang}\n"
                    )
                    f.write("=" * 50 + "\n\n")
            # 仅当文件存在但为空时才写入头部
            elif os.path.getsize(self.file_path) == 0:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write(f"{self.output_format} - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(
                        f"{self._get_label('source_language_label')}: {self.source_lang} -> "
                        f"{self._get_label('target_language_label')}: {self.target_lang}\n"
                    )
                    f.write("=" * 50 + "\n\n")
        except IOError as e:
            if self.logger:
                self.logger.error(f"写入文件头部时出错: {str(e)}")
            else:
                print(f"写入文件头部时出错: {str(e)}")

    def report_result_status(self):
        """报告翻译结果的最终状态（文件是否存在及保存路径）"""
        result_file = self.get_file_path()
        status = self._get_label('translation_complete')
        file_exists = result_file and os.path.exists(result_file)
        # 检查是否有实际翻译内容
        has_translations = len(self.all_translations) > 0

        # 如果有翻译内容但文件还未初始化，初始化文件
        if has_translations and not self.file_initialized:
            self._write_header()
            self.file_initialized = True
            # 重新写入所有翻译内容
            try:
                with open(self.file_path, 'a', encoding='utf-8') as f:
                    for original, translated in zip(self.all_originals, self.all_translations):
                        if self.output_format == self._get_label('original_translation_parallel'):
                            f.write(f"{self._get_label('original_text_label')}: {original}\n")
                            f.write(f"{self._get_label('translated_text_label')}: {translated}\n\n")
            except IOError as e:
                if self.logger:
                    self.logger.error(f"报告结果状态时写入内容出错: {str(e)}")

        # 如果没有实际翻译内容，删除空文件
        if file_exists and not has_translations:
            try:
                os.remove(result_file)
                # 稍微重构日志记录逻辑，确保coverage工具能正确识别
                logger = self.logger
                if logger:
                    log_message = f"删除空结果文件: {result_file}"
                    logger.info(log_message)
            except OSError as e:
                if self.logger:
                    self.logger.error(f"无法删除空结果文件: {e}")

        # 定义输出工具函数，统一处理日志和打印
        def output(msg):
            if self.logger:
                self.logger.info(msg)
            else:
                print(msg)

        if file_exists and has_translations:
            output(f"{self._get_label('translation_saved_to')}: {result_file}")
            output(f"{status}: {self._get_label('generated_file')} {os.path.basename(result_file)}")
        else:
            output(self._get_label('no_translation_result'))
            output(f"{status}: {self._get_label('no_result_generated')}")



    def _get_label(self, key):
        """根据语言配置获取对应的标签文本"""
        # 获取当前语言的标签集，默认为中文
        lang_labels = LANGUAGE_LABELS.get(self.language, LANGUAGE_LABELS['zh'])
        # 返回指定键的标签值
        return getattr(lang_labels, key, '')

    # pylint: disable=R0914
    def _parse_content(self, body):
        """解析内容获取原文和译文列表"""
        originals = []
        translations = []
        original_label = self._get_label('original_text_label') + ": "
        translated_label = self._get_label('translated_text_label') + ": "
        all_originals_label = self._get_label('all_originals_label')
        all_translations_label = self._get_label('all_translations_label')

        # 解析原译对照格式
        if original_label in body and translated_label in body:
            # 使用动态构建的正则表达式模式
            pattern = (
                    rf"{re.escape(original_label)}(.*?)\n"
                    rf"{re.escape(translated_label)}(.*?)"
                    rf"(?=\n{re.escape(original_label)}|\Z)"
                )
            matches = re.findall(pattern, body, re.DOTALL)
            for orig, trans in matches:
                cleaned_orig = orig.strip().replace('\n', ' ')
                cleaned_trans = trans.strip().replace('\n', ' ')
                if cleaned_orig and cleaned_trans:  # 确保内容不为空
                    originals.append(cleaned_orig)
                    translations.append(cleaned_trans)

        # 解析原译分开格式
        elif all_originals_label in body and all_translations_label in body:
            # 使用更精确的分割方式
            parts = re.split(
                    rf"({re.escape(all_originals_label)}|"
                    rf"{re.escape(all_translations_label)})",
                    body
                )
            if len(parts) >= 5:  # 确保有足够的部分
                # 提取原文部分
                orig_text = parts[2].strip()
                if orig_text:
                    original_lines = [line.strip() for line in orig_text.split('\n')
                                     if line.strip()]
                    originals.extend(original_lines)

                # 提取译文部分
                trans_text = parts[4].strip()
                if trans_text:
                    translation_lines = [line.strip() for line in trans_text.split('\n')
                                        if line.strip()]
                    translations.extend(translation_lines)

        # 确保原文和译文数量匹配
        min_count = min(len(originals), len(translations))
        return originals[:min_count], translations[:min_count]

    @classmethod
    # pylint: disable=R0912, R0914, R0915
    def convert_file_format(cls, file_path, new_format, language='zh'):
        """转换单个文件的格式"""
        # 获取当前语言的标签集，默认为中文
        lang_labels = LANGUAGE_LABELS.get(language, LANGUAGE_LABELS['zh'])

        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析头部信息和内容
            separator = "=" * 50
            header_end_index = content.find(separator)
            if header_end_index == -1:
                raise ValueError(lang_labels.file_conversion_failed)

            header_end = header_end_index + len(separator)
            header = content[:header_end] + "\n"
            body = content[header_end:].strip()

            if not body:
                raise ValueError(lang_labels.no_valid_translations)

            originals = []
            translations = []

            # 尝试多种解析方法
            parsed = False

            # 解析原译对照格式
            if (not parsed and
                    lang_labels.original_text_label in body and
                    lang_labels.translated_text_label in body):
                # 改进正则表达式，提高匹配可靠性
                pattern = (
                    rf"{re.escape(lang_labels.original_text_label)}: (.*?)\n"
                    rf"{re.escape(lang_labels.translated_text_label)}: "
                    rf"(.*?)(?=\n"
                    rf"{re.escape(lang_labels.original_text_label)}: |\Z)")
                matches = re.findall(pattern, body, re.DOTALL)
                if matches:
                    for orig, trans in matches:
                        cleaned_orig = orig.strip().replace('\n', ' ')
                        cleaned_trans = trans.strip().replace('\n', ' ')
                        if cleaned_orig and cleaned_trans:  # 确保内容不为空
                            originals.append(cleaned_orig)
                            translations.append(cleaned_trans)
                    parsed = True

            # 解析原译分开格式
            if not parsed and lang_labels.all_originals_label in body \
               and lang_labels.all_translations_label in body:
                # 改进分割逻辑，更可靠地提取内容
                all_origins_pos = body.find(lang_labels.all_originals_label)
                all_trans_pos = body.find(lang_labels.all_translations_label)

                if all_origins_pos != -1 and all_trans_pos != -1:
                    # 确保原文部分在译文部分之前
                    if all_origins_pos < all_trans_pos:
                        orig_text = body[all_origins_pos + \
                                        len(lang_labels.all_originals_label):all_trans_pos].strip()
                        trans_text = body[all_trans_pos + \
                                        len(lang_labels.all_translations_label):].strip()

                        if orig_text:
                            originals = [line.strip() for line in orig_text.split('\n')
                                       if line.strip()]
                        if trans_text:
                            translations = [line.strip() for line in trans_text.split('\n')
                                           if line.strip()]

                        if originals and translations:
                            parsed = True

            # 确保原文和译文数量匹配且不为空
            min_count = min(len(originals), len(translations))
            originals = originals[:min_count]
            translations = translations[:min_count]

            # 严格验证内容，不允许创建只有header的文件
            if not originals or not translations:
                raise ValueError(lang_labels.no_valid_translations)

            # 写入转换后的内容
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入头部
                f.write(header)

                if new_format == lang_labels.original_translation_parallel:
                    # 转换为原译对照
                    for orig, trans in zip(originals, translations):
                        f.write(f"{lang_labels.original_text_label}: {orig}\n")
                        f.write(f"{lang_labels.translated_text_label}: {trans}\n\n")
                else:
                    # 转换为原译分开
                    f.write(f"{lang_labels.all_originals_label}\n")
                    for orig in originals:
                        f.write(f"{orig}\n")

                    f.write(f"\n{lang_labels.all_translations_label}\n")
                    for trans in translations:
                        f.write(f"{trans}\n")

            return True
        except (OSError, re.error, UnicodeDecodeError, ValueError) as e:
            error_msg = f"{lang_labels.error_converting_file}{file_path}" \
                         f"{lang_labels.error_occurred}: {str(e)}"
            print(error_msg)
            return False

    def convert_result_format(self, output_format, format_options, parent):
        """转换result文件夹下所有结果文件的格式"""
        # 获取目标格式
        format_text = output_format.currentText()
        target_format = format_options[format_text]

        # 检查result文件夹是否存在
        if not os.path.exists(Config.RESULT_DIR):
            message_center.show_warning(
                self._get_label('prompt'),
                self._get_label('no_result_folder'),
                parent=parent
            )
            return

        # 获取所有结果文件
        txt_files = [f for f in os.listdir(Config.RESULT_DIR)
                     if f.endswith('.txt') and f.startswith('translate_result_')]

        if not txt_files:
            message_center.show_warning(
                self._get_label('prompt'),
                self._get_label('no_result_files'),
                parent=parent
            )
            return

        # 转换所有文件
        success_count = 0
        total_count = len(txt_files)

        for file_name in txt_files:
            file_path = os.path.join(Config.RESULT_DIR, file_name)
            if ResultRecorder.convert_file_format(file_path, target_format, self.language):
                success_count += 1

        # 显示结果
        if success_count == total_count:
            message_center.show_information(
                self._get_label('success'),
                self._get_label('file_converted').format(format=format_text),
                parent=parent
            )
        elif success_count > 0:
            message_center.show_warning(
                self._get_label('prompt'),
                f"部分文件转换成功: {success_count}/{total_count}",
                parent=parent
            )
        else:
            message_center.show_critical(
                self._get_label('error'),
                self._get_label('file_conversion_failed'),
                parent=parent
            )
