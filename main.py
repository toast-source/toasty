import sys
import os
import json
import re
import subprocess
import tempfile
import wordninja
from thefuzz import process, fuzz
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QWidget, QPushButton, QFileDialog, QTextEdit, QMessageBox,
                             QListWidget, QHBoxLayout, QLineEdit, QDialog, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout,
                             QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# --- Global Dictionary Configuration ---
DICT_FILE_PATH = "custom_dictionary.json"
DEFAULT_DICTIONARY = [
    "Attack", "Ready", "Groggy", "End", "Loop", "Channeling", "Break",
    "Idle", "Walk", "Run", "Jump", "Fall", "Hit", "Dead", "Skill",
    "Ultimate", "Phase", "Start", "Intro", "Outro"
]

def load_dictionary():
    if os.path.exists(DICT_FILE_PATH):
        try:
            with open(DICT_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_DICTIONARY.copy()

def save_dictionary(words_list):
    with open(DICT_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(words_list, f, indent=4, ensure_ascii=False)

def correct_spelling(word, custom_dict, threshold=80):
    if len(word) <= 2:
        return word.capitalize(), False
        
    word_lower = word.lower()
    dict_lower = {w.lower(): w for w in custom_dict}
    
    if word_lower in dict_lower:
        return dict_lower[word_lower], False

    choices = list(dict_lower.keys())
    best_match = process.extractOne(word_lower, choices, scorer=fuzz.ratio)
    
    if best_match and best_match[1] >= threshold:
        corrected_lower = best_match[0]
        corrected_word = dict_lower[corrected_lower]
        return corrected_word, True
        
    return word.capitalize(), False

def format_tag_name(name, custom_dict):
    is_loop = False
    spelling_corrected = False
    
    if "_(Loop)" in name:
        is_loop = True
        name = name.replace("_(Loop)", "")
    elif "(Loop)" in name:
        is_loop = True
        name = name.replace("(Loop)", "")
        
    parts = name.split('_')
    formatted_parts = []
    
    for part in parts:
        if not part:
            continue
        
        # 1. Split by CamelCase/PascalCase First
        sub_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', part)
        if not sub_words:
            sub_words = [part]
            
        final_sub_words = []
        for sw in sub_words:
            # 1. 먼저 전체 단어에 대해 스펠링 교정을 시도합니다
            corrected_sw, was_corrected = correct_spelling(sw, custom_dict)
            
            if was_corrected:
                spelling_corrected = True
                final_sub_words.append(corrected_sw)
            elif sw.islower() and len(sw) >= 4:
                # 2. 스펠링 교정이 안 되었고, 전부 소문자라면 wordninja로 쪼개기 시도
                split_sw = wordninja.split(sw)
                
                if len(split_sw) > 1:
                    for w in split_sw:
                        corrected_w, was_corrected_w = correct_spelling(w, custom_dict)
                        if was_corrected_w:
                            spelling_corrected = True
                        final_sub_words.append(corrected_w)
                else:
                    final_sub_words.append(sw[0].upper() + sw[1:])
            else:
                # 3. 그 외의 경우 단순히 첫 글자만 대문자로 처리
                final_sub_words.append(sw[0].upper() + sw[1:])
                
        formatted_parts.append("".join(final_sub_words))
        
    final_name = "_".join(formatted_parts)
    if is_loop:
        final_name += "_(Loop)"
        
    return final_name, is_loop, spelling_corrected

class AnalysisThread(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, files, aseprite_path):
        super().__init__()
        self.files = files
        self.aseprite_path = aseprite_path

    def run(self):
        results = {}
        for file_path in self.files:
            try:
                tags = self.get_tags_from_file(file_path)
                results[file_path] = tags
            except Exception as e:
                self.error_signal.emit(f"Error reading {os.path.basename(file_path)}: {str(e)}")
        self.result_signal.emit(results)

    def get_tags_from_file(self, file_path):
        json_fd, json_path = tempfile.mkstemp(suffix=".json")
        os.close(json_fd)
        
        lua_script = f"""
local sprite = app.sprite
if not sprite then return end
local file = io.open(app.params["out_json"], "w")
file:write("[")
for i, tag in ipairs(sprite.tags) do
    local name = string.gsub(tag.name, '"', '\\\\"')
    file:write('{{"name":"' .. name .. '", "repeats":' .. tostring(tag.repeats) .. '}}')
    if i < #sprite.tags then file:write(",") end
end
file:write("]")
file:close()
"""
        lua_fd, lua_path = tempfile.mkstemp(suffix=".lua")
        with os.fdopen(lua_fd, 'w', encoding='utf-8') as f:
            f.write(lua_script)

        cmd = [
            self.aseprite_path, "-b", file_path,
            "--script-param", f"out_json={json_path}",
            "--script", lua_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            os.remove(json_path)
            os.remove(lua_path)
            raise Exception("Failed to read tags.")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = f.read()
            tags = json.loads(data) if data else []

        os.remove(json_path)
        os.remove(lua_path)
        return tags

class ApplyThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, file_modifications, aseprite_path):
        super().__init__()
        self.file_modifications = file_modifications 
        self.aseprite_path = aseprite_path

    def run(self):
        for file_path, mods in self.file_modifications.items():
            if not mods:
                continue
            try:
                self.apply_to_file(file_path, mods)
            except Exception as e:
                self.error_signal.emit(f"Error modifying {os.path.basename(file_path)}: {str(e)}")
        self.finished_signal.emit()

    def apply_to_file(self, file_path, mods):
        lua_script = """
local sprite = app.sprite
if not sprite then return end
local function set_tag(old_name, new_name, set_repeat)
    for i, tag in ipairs(sprite.tags) do
        if tag.name == old_name then
            tag.name = new_name
            if set_repeat then
                tag.repeats = 0
            end
        end
    end
end
"""
        for old_name, new_name, set_repeat in mods:
            escaped_old = old_name.replace('"', '\\"')
            escaped_new = new_name.replace('"', '\\"')
            set_repeat_str = "true" if set_repeat else "false"
            lua_script += f'\nset_tag("{escaped_old}", "{escaped_new}", {set_repeat_str})'
            self.log_signal.emit(f"[{os.path.basename(file_path)}] {old_name} => {new_name}")

        lua_script += f'\nsprite:saveAs("{file_path.replace(chr(92), "/")}")\n'

        lua_fd, lua_path = tempfile.mkstemp(suffix=".lua")
        with os.fdopen(lua_fd, 'w', encoding='utf-8') as f:
            f.write(lua_script)

        cmd = [self.aseprite_path, "-b", file_path, "--script", lua_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(lua_path)
        
        if result.returncode != 0:
            raise Exception("Failed to save.")

class DictEditorDialog(QDialog):
    def __init__(self, parent, current_dict):
        super().__init__(parent)
        self.setWindowTitle("단어 사전 편집기 (Dictionary Editor)")
        self.resize(400, 500)
        self.current_dict = current_dict
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("사전에 등록된 단어들 (스펠링 교정의 기준이 됩니다):"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText("\n".join(self.current_dict))
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장 (Save)")
        btn_cancel = QPushButton("취소 (Cancel)")
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        btn_save.clicked.connect(self.save_and_accept)
        btn_cancel.clicked.connect(self.reject)
        
    def save_and_accept(self):
        text = self.text_edit.toPlainText()
        new_words = [word.strip() for word in text.split('\n') if word.strip()]
        self.current_dict = list(dict.fromkeys(new_words))
        self.accept()

class ReportDialog(QDialog):
    def __init__(self, parent, analysis_data, custom_dict, replace_pairs=None):
        super().__init__(parent)
        self.setWindowTitle("검수 리포트 (Check Report) - 체크 해제 시 적용 안됨")
        self.resize(1000, 700)
        self.analysis_data = analysis_data
        self.custom_dict = custom_dict
        self.replace_pairs = replace_pairs or []
        self.modifications_to_apply = {} 
        self.checkboxes = []
        self.issue_types_found = set()

        layout = QVBoxLayout(self)
        
        filter_group = QGroupBox("이슈별 일괄 선택/해제 (Batch Selection by Issue)")
        self.filter_layout = QHBoxLayout()
        filter_group.setLayout(self.filter_layout)
        layout.addWidget(filter_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["적용(Apply)", "File Name", "Original Tag", "New Tag", "Issue"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.table)

        self.populate_table()
        self.create_filter_checkboxes()

        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("선택 항목 수정 및 저장 (Apply & Save Checked)")
        self.btn_cancel = QPushButton("취소 (Cancel)")
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self.confirm_and_accept)

    def populate_table(self):
        row_idx = 0
        for file_path, tags in self.analysis_data.items():
            for tag in tags:
                original_name = tag['name']
                
                # Apply all Find & Replace pairs in sequence
                intermediate_name = original_name
                for f_str, r_str in self.replace_pairs:
                    intermediate_name = intermediate_name.replace(f_str, r_str)
                
                new_name, is_loop, spelling_corrected = format_tag_name(intermediate_name, self.custom_dict)
                set_repeat = is_loop and tag.get('repeats') != 0

                issues = []
                if original_name != intermediate_name:
                    issues.append("일괄 단어 치환")
                    self.issue_types_found.add("일괄 단어 치환")
                if spelling_corrected:
                    issues.append("스펠링 교정")
                    self.issue_types_found.add("스펠링 교정")
                elif intermediate_name != new_name:
                    issues.append("네이밍 규칙 위반")
                    self.issue_types_found.add("네이밍 규칙 위반")
                
                if set_repeat:
                    issues.append("Loop 속성(Repeat) 누락")
                    self.issue_types_found.add("Loop 속성(Repeat) 누락")

                if issues:
                    self.table.insertRow(row_idx)
                    
                    chk_widget = QWidget()
                    chk_layout = QHBoxLayout(chk_widget)
                    chk_box = QCheckBox()
                    chk_box.setChecked(True)
                    chk_layout.addWidget(chk_box)
                    chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    chk_layout.setContentsMargins(0,0,0,0)
                    self.table.setCellWidget(row_idx, 0, chk_widget)
                    
                    issue_text = ", ".join(issues)
                    
                    self.checkboxes.append({
                        'checkbox': chk_box,
                        'file_path': file_path,
                        'old_name': original_name,
                        'new_name': new_name,
                        'set_repeat': set_repeat,
                        'issues': issue_text
                    })
                    
                    self.table.setItem(row_idx, 1, QTableWidgetItem(os.path.basename(file_path)))
                    self.table.setItem(row_idx, 2, QTableWidgetItem(original_name))
                    
                    new_item = QTableWidgetItem(new_name)
                    new_item.setForeground(Qt.GlobalColor.blue)
                    self.table.setItem(row_idx, 3, new_item)
                    
                    issue_item = QTableWidgetItem(issue_text)
                    issue_item.setForeground(Qt.GlobalColor.red)
                    self.table.setItem(row_idx, 4, issue_item)
                    
                    row_idx += 1

    def create_filter_checkboxes(self):
        self.chk_all = QCheckBox("전체 선택/해제 (Select All)")
        self.chk_all.setChecked(True)
        self.chk_all.setStyleSheet("font-weight: bold;")
        self.chk_all.stateChanged.connect(self.toggle_all)
        self.filter_layout.addWidget(self.chk_all)
        
        self.issue_filter_boxes = {}
        for issue_type in sorted(list(self.issue_types_found)):
            chk = QCheckBox(issue_type)
            chk.setChecked(True)
            chk.stateChanged.connect(lambda state, itype=issue_type: self.toggle_by_issue(itype, state))
            self.filter_layout.addWidget(chk)
            self.issue_filter_boxes[issue_type] = chk
            
        self.filter_layout.addStretch()

    def toggle_all(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        for chk in self.issue_filter_boxes.values():
            chk.blockSignals(True)
            chk.setChecked(is_checked)
            chk.blockSignals(False)
            
        for item in self.checkboxes:
            item['checkbox'].setChecked(is_checked)

    def toggle_by_issue(self, issue_type, state):
        is_checked = state == Qt.CheckState.Checked.value
        for item in self.checkboxes:
            if issue_type in item['issues']:
                item['checkbox'].setChecked(is_checked)

    def confirm_and_accept(self):
        for item in self.checkboxes:
            if item['checkbox'].isChecked():
                path = item['file_path']
                if path not in self.modifications_to_apply:
                    self.modifications_to_apply[path] = []
                self.modifications_to_apply[path].append((item['old_name'], item['new_name'], item['set_repeat']))

        if not self.modifications_to_apply:
            QMessageBox.information(self, "알림", "선택된 항목이 없습니다.")
            self.reject()
            return
            
        reply = QMessageBox.question(
            self, "저장 확인", 
            "선택한 변경사항을 원본 파일에 덮어씌워 저장하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

class DropListWidget(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile().lower().endswith(('.ase', '.aseprite'))]
        if files:
            self.files_dropped.emit(files)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aseprite Tag Master (Advanced Mode)")
        self.resize(800, 750)

        self.aseprite_path = r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\aseprite.exe"
        self.loaded_files = set()
        self.custom_dict = load_dictionary()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Path & Dict Section
        path_layout = QGridLayout()
        self.path_label = QLabel(f"Aseprite Path: {self.aseprite_path}")
        btn_path = QPushButton("경로 변경")
        btn_path.clicked.connect(self.change_aseprite_path)
        
        btn_dict = QPushButton("📖 단어 사전 편집기 (Dictionary)")
        btn_dict.clicked.connect(self.open_dict_editor)
        
        path_layout.addWidget(self.path_label, 0, 0)
        path_layout.addWidget(btn_path, 0, 1)
        path_layout.addWidget(btn_dict, 1, 1)
        layout.addLayout(path_layout)

        # File List Section
        layout.addWidget(QLabel("여기에 .ase / .aseprite 파일들을 드래그 앤 드롭 하세요:"))
        self.file_list = DropListWidget()
        self.file_list.files_dropped.connect(self.add_files)
        layout.addWidget(self.file_list)
        
        btn_remove = QPushButton("선택한 파일 목록에서 제거")
        btn_remove.clicked.connect(self.remove_selected_files)
        layout.addWidget(btn_remove)

        # Batch Replace Section (Dynamic List)
        self.replace_group = QGroupBox("다중 일괄 단어 치환 (선택사항)")
        replace_layout = QVBoxLayout()
        
        btn_replace_ctrl_layout = QHBoxLayout()
        self.btn_add_replace = QPushButton("+ 치환 단어쌍 추가")
        self.btn_add_replace.clicked.connect(self.add_replace_row)
        self.btn_del_replace = QPushButton("- 선택된 항목 삭제")
        self.btn_del_replace.clicked.connect(self.del_replace_row)
        btn_replace_ctrl_layout.addWidget(self.btn_add_replace)
        btn_replace_ctrl_layout.addWidget(self.btn_del_replace)
        btn_replace_ctrl_layout.addStretch()
        replace_layout.addLayout(btn_replace_ctrl_layout)
        
        self.replace_table = QTableWidget(0, 2)
        self.replace_table.setHorizontalHeaderLabels(["찾을 단어 (Find)", "바꿀 단어 (Replace)"])
        self.replace_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.replace_table.setMaximumHeight(150)
        self.add_replace_row() # 기본 1행 추가
        replace_layout.addWidget(self.replace_table)
        
        self.replace_group.setLayout(replace_layout)
        layout.addWidget(self.replace_group)

        # Bottom Action Buttons
        action_layout = QHBoxLayout()
        btn_analyze = QPushButton("검수 및 수정 리포트 보기 (Analyze)")
        btn_analyze.setMinimumHeight(50)
        btn_analyze.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        btn_analyze.clicked.connect(self.start_analysis)
        action_layout.addWidget(btn_analyze)
        layout.addLayout(action_layout)

        # Log Box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

    def change_aseprite_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select aseprite.exe", "", "Executable (*.exe)")
        if path:
            self.aseprite_path = path
            self.path_label.setText(f"Aseprite Path: {self.aseprite_path}")

    def open_dict_editor(self):
        dialog = DictEditorDialog(self, self.custom_dict)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.custom_dict = dialog.current_dict
            save_dictionary(self.custom_dict)
            self.log_box.append("단어 사전이 업데이트 되었습니다.")

    def add_files(self, files):
        for f in files:
            if f not in self.loaded_files:
                self.loaded_files.add(f)
                self.file_list.addItem(f)
        self.log_box.append(f"{len(files)}개 파일이 목록에 추가되었습니다.")

    def remove_selected_files(self):
        for item in self.file_list.selectedItems():
            self.loaded_files.remove(item.text())
            self.file_list.takeItem(self.file_list.row(item))

    def add_replace_row(self):
        row = self.replace_table.rowCount()
        self.replace_table.insertRow(row)
        self.replace_table.setItem(row, 0, QTableWidgetItem(""))
        self.replace_table.setItem(row, 1, QTableWidgetItem(""))

    def del_replace_row(self):
        current_row = self.replace_table.currentRow()
        if current_row >= 0:
            self.replace_table.removeRow(current_row)

    def get_replace_pairs(self):
        pairs = []
        for i in range(self.replace_table.rowCount()):
            find_item = self.replace_table.item(i, 0)
            rep_item = self.replace_table.item(i, 1)
            f_str = find_item.text().strip() if find_item else ""
            r_str = rep_item.text().strip() if rep_item else ""
            if f_str:
                pairs.append((f_str, r_str))
        return pairs

    def start_analysis(self):
        if not self.loaded_files:
            QMessageBox.warning(self, "경고", "먼저 파일을 드래그 앤 드롭으로 추가해주세요.")
            return
        if not os.path.exists(self.aseprite_path):
            QMessageBox.critical(self, "에러", "Aseprite 실행 파일을 찾을 수 없습니다.")
            return

        self.log_box.append("파일 분석 중... (Aseprite 백그라운드 실행)")
        self.setEnabled(False)

        self.analysis_thread = AnalysisThread(list(self.loaded_files), self.aseprite_path)
        self.analysis_thread.result_signal.connect(self.show_report)
        self.analysis_thread.error_signal.connect(lambda e: self.log_box.append(f"<font color='red'>{e}</font>"))
        self.analysis_thread.start()

    def show_report(self, analysis_data):
        self.setEnabled(True)
        pairs = self.get_replace_pairs()
        dialog = ReportDialog(self, analysis_data, self.custom_dict, pairs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_modifications(dialog.modifications_to_apply)
        else:
            self.log_box.append("작업이 취소되었습니다.")

    def apply_modifications(self, mods):
        self.log_box.append("파일 수정 및 저장 중...")
        self.setEnabled(False)
        self.apply_thread = ApplyThread(mods, self.aseprite_path)
        self.apply_thread.log_signal.connect(self.log_box.append)
        self.apply_thread.error_signal.connect(lambda e: self.log_box.append(f"<font color='red'>{e}</font>"))
        self.apply_thread.finished_signal.connect(self.on_apply_finished)
        self.apply_thread.start()

    def on_apply_finished(self):
        self.setEnabled(True)
        self.log_box.append("=== 모든 수정 및 저장이 완료되었습니다! ===")
        QMessageBox.information(self, "완료", "파일 저장이 완료되었습니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
