import os
import json
import pymzml
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5 import QtWidgets, QtGui, QtCore

from utils.roi import get_ROIs, ROI
from utils.roi import construct_ROI
from utils.plot import PlotWindow
from utils.show_list import FileListWidget, GetFolderWidget, ROIListWidget
from utils.threading import Worker


class ReAnnotationParameterWindow(QtWidgets.QDialog):
    def __init__(self, parent: PlotWindow):
        self.mode = 'reannotation'
        self.parent = parent
        super().__init__(parent)
        self.setWindowTitle('继续标注')

        save_to_label = QtWidgets.QLabel()
        save_to_label.setText('选择已生成过ROI的目录')
        self.folder_widget = GetFolderWidget()

        self.run_button = QtWidgets.QPushButton('继续')
        self.run_button.clicked.connect(self.start_reannotation)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(save_to_label)
        main_layout.addWidget(self.folder_widget)
        main_layout.addWidget(self.run_button)

        self.setLayout(main_layout)

    def start_reannotation(self):
        folder = self.folder_widget.get_folder()
        subwindow = AnnotationMainWindow([], folder, None, None,
                                         None, self.mode, None,
                                         None, parent=self.parent)
        subwindow.show()
        self.close()


class AnnotationParameterWindow(QtWidgets.QDialog):
    def __init__(self, files, mode, parent: PlotWindow):
        self.mode = mode
        self.parent = parent
        super().__init__(parent)
        self.setWindowTitle('生成ROI的参数设置')

        self.files = files
        self.description = None
        self.file_prefix = None
        self.file_suffix = None
        self.minimum_peak_points = None
        self.dropped_points = 3
        self.folder = None

        self._init_ui()

        self.list_of_files.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_of_files.connectDoubleClick(self.get_freq)  # 双击获取扫描频率
    def _init_ui(self):
        # file and folder selection
        choose_file_label = QtWidgets.QLabel()
        choose_file_label.setText('选择标注文件：')
        self.list_of_files = FileListWidget()
        for file in self.files:
            self.list_of_files.addFile(file)

        save_to_label = QtWidgets.QLabel()
        save_to_label.setText('选择保存标注文件的目录（请选择空目录）：')
        self.folder_widget = GetFolderWidget()

        file_layout = QtWidgets.QVBoxLayout()
        file_layout.addWidget(choose_file_label)
        file_layout.addWidget(self.list_of_files)
        file_layout.addWidget(save_to_label)
        file_layout.addWidget(self.folder_widget)

        # parameters selection

        instrumental_label = QtWidgets.QLabel()
        instrumental_label.setText('*双击文件可获取扫描时长&频率')
        self.instrumental_getter = QtWidgets.QLabel()
        self.instrumental_getter.setText('total time = , freq = ')

        prefix_label = QtWidgets.QLabel()
        prefix_label.setText('文件前缀：')
        self.prefix_getter = QtWidgets.QLineEdit(self)
        self.prefix_getter.setText('Example')

        suffix_label = QtWidgets.QLabel()
        suffix_label.setText('文件序号 (后缀名， 随着标注依次+1)：')
        self.suffix_getter = QtWidgets.QLineEdit(self)
        self.suffix_getter.setText('0')  # TODO:改为1，数组起始也要修改

        mz_label = QtWidgets.QLabel()
        mz_label.setText('m/z deviation:')
        self.mz_getter = QtWidgets.QLineEdit(self)
        self.mz_getter.setText('0.005')

        roi_points_label = QtWidgets.QLabel()
        roi_points_label.setText('ROI的最小长度（扫描数）：')
        self.roi_points_getter = QtWidgets.QLineEdit(self)
        self.roi_points_getter.setText('15')

        dropped_points_label = QtWidgets.QLabel()
        dropped_points_label.setText('ROI截止的连续零点个数：')
        self.dropped_points_getter = QtWidgets.QLineEdit(self)
        self.dropped_points_getter.setText('3')

        intensity_threshold_label = QtWidgets.QLabel()
        intensity_threshold_label.setText('最小强度阈值：')
        self.intensity_threshold_getter = QtWidgets.QLineEdit(self)
        self.intensity_threshold_getter.setText('1000')

        run_button = QtWidgets.QPushButton('生成')
        run_button.clicked.connect(self._run_button)

        parameter_layout = QtWidgets.QVBoxLayout()
        parameter_layout.addWidget(instrumental_label)
        parameter_layout.addWidget(self.instrumental_getter)
        parameter_layout.addWidget(prefix_label)
        parameter_layout.addWidget(self.prefix_getter)
        parameter_layout.addWidget(suffix_label)
        parameter_layout.addWidget(self.suffix_getter)
        parameter_layout.addWidget(mz_label)
        parameter_layout.addWidget(self.mz_getter)
        parameter_layout.addWidget(roi_points_label)
        parameter_layout.addWidget(self.roi_points_getter)
        parameter_layout.addWidget(dropped_points_label)
        parameter_layout.addWidget(self.dropped_points_getter)
        parameter_layout.addWidget(intensity_threshold_label)
        parameter_layout.addWidget(self.intensity_threshold_getter)
        parameter_layout.addWidget(run_button)

        # main layout
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(file_layout, 2)
        main_layout.addLayout(parameter_layout, 8)

        self.setLayout(main_layout)

    def _run_button(self):
        try:
            self.description = self.instrumental_getter.text() + ', intensity_thr = ' + self.intensity_threshold_getter.text()
            self.file_prefix = self.prefix_getter.text()
            self.file_suffix = int(self.suffix_getter.text())
            delta_mz = float(self.mz_getter.text())
            min_points = int(self.roi_points_getter.text())
            dropped_points = int(self.dropped_points_getter.text())
            intensity_threshold = int(self.intensity_threshold_getter.text())

            self.folder = self.folder_widget.get_folder()
            path2mzml = None
            for file in self.list_of_files.selectedItems():
                path2mzml = self.list_of_files.file2path[file.text()]
            if path2mzml is None:
                raise ValueError

            worker = Worker(get_ROIs, path2mzml, delta_mz, min_points, intensity_threshold, dropped_points)
            worker.signals.result.connect(self._save)
            worker.signals.result.connect(self._start_annotation)
            self.parent.run_thread('构建ROI并保存到指定目录：', worker)  # 进度条

            self.close()
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText("请检查：\n1.是否已选中一个待标注文件\n2.最小ROI长度及连续零点数应输入整数")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    def _save(self, rois):
        for file_suffix in range(0, len(rois)):
            dropped_points = int(self.dropped_points_getter.text())
            filename = f'{self.file_prefix}_{file_suffix}.json'
            plotted_path = os.path.join(self.folder, filename)
            code = os.path.basename(plotted_path)
            code = code[:code.rfind('.')]
            # print('saving, plotted_path = ', plotted_path, 'rois[] = ', rois[file_suffix])
            ROI.save_annotated(rois[file_suffix], plotted_path, code, 'unmarked',
                               drop_points=dropped_points, description=self.description)
            file_suffix += 1

    def _start_annotation(self, rois):
        dropped_points = int(self.dropped_points_getter.text())
        subwindow = AnnotationMainWindow(rois, self.folder, self.file_prefix, self.file_suffix,
                                         self.description, self.mode, self.minimum_peak_points,
                                         dropped_points, parent=self.parent)

        subwindow.show()

    def get_freq(self, item):
        spectrum_count = 0
        t = 0
        measure = 'second'
        get_selected_files = self.list_of_files.selectedItems()
        for file in get_selected_files:
            filename = file.text()
            path2file = self.list_of_files.file2path[filename]
            run = pymzml.run.Reader(path2file)
            spectrum_count = run.get_spectrum_count()  # scan总数
            # freq = run.scan_time_in_minutes()
            for spectrum in run:
                if spectrum.ID == spectrum_count:  # 读取扫描时长
                    t, measure = spectrum.scan_time  # get scan time 扫描总时长
                    print(spectrum.ID, spectrum_count, t, measure)
        if measure == 'millisecond':
            measure = 'ms'
            frequency = spectrum_count / t * 1000
        elif measure == 'minute':
            measure = 'min'
            frequency = spectrum_count / t / 60
        elif measure == 'hour':
            measure = 'h'
            frequency = spectrum_count / t / 360
        else:
            measure = 's'
            frequency = spectrum_count / t
        t = "{:.3f}".format(t)
        frequency = "{:.2f}".format(frequency)

        time = str(t)
        freq = str(frequency)
        self.instrumental_getter.setText('total time = ' + time + measure + ', freq = ' + freq + 'Hz')


class AnnotationMainWindow(QtWidgets.QDialog):
    def __init__(self, ROIs, folder, file_prefix, file_suffix, description, mode,
                 minimum_peak_points, dropped_points, parent=None):
        super().__init__(parent)
        self.setWindowTitle('annotation window')
        self.file_prefix = file_prefix
        self.file_suffix = file_suffix
        self.description = description
        self.current_description = description
        self.folder = folder
        self.mode = mode
        self.dropped_points = dropped_points
        self.plotted_roi = None
        self.plotted_path = None
        self.plotted_item = None  # data reannotation
        self.current_flag = False

        self.ROIs = ROIs

        self.figure = plt.figure()  # a figure instance to plot on
        self.canvas = FigureCanvas(self.figure)

        self.rois_list = ROIListWidget()  # 已标注的ROI列表
        self.rois_list.connectRightClick(self.file_right_click)
        self.rois_list.connectDoubleClick(self.file_double_click)

        files = []
        for created_file in os.listdir(self.folder):
            if created_file.endswith('.json'):
                begin = created_file.find('_') + 1
                end = created_file.find('.json')
                code = int(created_file[begin:end])
                files.append((code, created_file))
        for _, file in sorted(files):
            self.rois_list.addFile(os.path.join(self.folder, file))

        self._init_ui()  # initialize user interface
        if mode != 'reannotation':
            self.plot_current()  # initial plot

    def _init_ui(self):
        """
        Initialize all buttons and layouts.
        """
        # canvas layout
        toolbar = NavigationToolbar(self.canvas, self)
        canvas_layout = QtWidgets.QVBoxLayout()
        canvas_layout.addWidget(toolbar)
        canvas_layout.addWidget(self.canvas)

        # ROI list layout
        self.roi_cnt = QtWidgets.QLabel(self)
        if self.mode != 'reannotation':
            roi_label = QtWidgets.QLabel('当前文件ROI总数：')
            self.roi_cnt.setNum(len(self.ROIs))  # 获取当前生成ROI的个数
        else:
            roi_label = QtWidgets.QLabel('当前目录下ROI总数：')  # 当模式为继续标注时，读取目录下的文件总数
            file_cnt = self.rois_list.count()
            self.roi_cnt.setNum(file_cnt)
        # annotation progress
        print('ROI个数', len(self.ROIs))
        roi_list_layout = QtWidgets.QVBoxLayout()
        roi_progress = QtWidgets.QHBoxLayout()
        roi_progress.addWidget(roi_label)
        roi_progress.addWidget(self.roi_cnt)
        roi_list_layout.addLayout(roi_progress)
        roi_list_layout.addWidget(self.rois_list)

        # canvas and ROI list layout
        canvas_files_layout = QtWidgets.QHBoxLayout()
        # canvas_files_layout.addWidget(self.raw_rois_list, 20)
        canvas_files_layout.addLayout(canvas_layout, 80)
        canvas_files_layout.addLayout(roi_list_layout, 20)

        # plot current button
        # plot_current_button = QtWidgets.QPushButton('回到当前')
        # plot_current_button.clicked.connect(self.plot_current)

        # noise button
        noise_button = QtWidgets.QPushButton('0分（噪声）')
        noise_button.clicked.connect(self.noise)
        # one peak button
        peak_button = QtWidgets.QPushButton('单峰')
        peak_button.clicked.connect(self.peak)
        # two or more peaks button
        peaks_button = QtWidgets.QPushButton('多个峰')
        peaks_button.clicked.connect(self.peaks)
        # skip button
        skip_button = QtWidgets.QPushButton('Skip')
        skip_button.clicked.connect(self.skip)
        # plot chosen button
        # plot_chosen_button = QtWidgets.QPushButton('Plot chosen ROI')
        # plot_chosen_button.clicked.connect(self.press_plot_chosen)

        # button layout
        button_layout = QtWidgets.QHBoxLayout()
        # button_layout.addWidget(plot_current_button)
        button_layout.addWidget(noise_button)
        button_layout.addWidget(peak_button)
        button_layout.addWidget(peaks_button)
        button_layout.addWidget(skip_button)
        # button_layout.addWidget(plot_chosen_button)

        # main layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(canvas_files_layout)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    # Auxiliary methods
    def file_right_click(self):
        FileContextMenu(self)

    def file_double_click(self, item):
        self.plotted_item = item
        self.plot_chosen()

    def get_chosen(self):
        chosen_item = None
        for item in self.rois_list.selectedItems():
            chosen_item = item
        return chosen_item

    def close_file(self, item):
        if item == self.plotted_item:
            index = min(self.rois_list.row(self.plotted_item) + 1, self.rois_list.count() - 2)
            self.plotted_item = self.rois_list.item(index)
            self.plotted_item.setSelected(True)
            self.plot_chosen()
        self.rois_list.deleteFile(item)

    def delete_file(self, item):
        os.remove(self.rois_list.getPath(item))
        self.close_file(item)

    # Buttons
    def noise(self):
        code = os.path.basename(self.plotted_path)
        code = code[:code.rfind('.')]
        label = 0
        self.plotted_roi.save_annotated(self.plotted_path, code, label, description=self.current_description)
        self.rois_list.refresh_background(self.plotted_path)  # 更新列表背景

        if self.current_flag:
            self.current_flag = False
            # self.rois_list.addFile(self.plotted_path)
            self.file_suffix += 1
            self.plot_current()
        else:
            self.plotted_item.setSelected(False)
            index = min(self.rois_list.row(self.plotted_item) + 1, self.rois_list.count() - 1)
            self.plotted_item = self.rois_list.item(index)
            self.plotted_item.setSelected(True)
            self.plot_chosen()

    def peak(self):  # 单峰评分
        subwindow = OnePeakScoreWindow(self)
        subwindow.show()

    def peaks(self):  # 多峰标注
        subwindow = AnnotationGetNumberOfPeaksNovel(self)
        subwindow.show()

    def skip(self):
        if self.current_flag:
            self.file_suffix += 1
            self.current_flag = False
            self.plot_current()
        else:
            self.plotted_item.setSelected(False)
            index = min(self.rois_list.row(self.plotted_item) + 1, self.rois_list.count() - 1)
            self.plotted_item = self.rois_list.item(index)
            self.plotted_item.setSelected(True)
            self.plot_chosen()

    def save_auto_annotation(self):
        if self.current_flag:
            number_of_peaks = len(self.borders)
            begins = []
            ends = []
            for begin, end in self.borders:
                begins.append(int(begin))
                ends.append(int(end))
            intersections = []
            for i in range(number_of_peaks - 1):
                intersections.append(int(np.argmin(self.plotted_roi.i[ends[i]:begins[i+1]]) + ends[i]))

            code = os.path.basename(self.plotted_path)
            code = code[:code.rfind('.')]
            self.plotted_roi.save_annotated(self.plotted_path, int(self.label), code, number_of_peaks,
                                            begins, ends, intersections, self.description)

            self.current_flag = False
            self.rois_list.addFile(self.plotted_path)
            self.file_suffix += 1
            self.plot_current()

    def press_plot_chosen(self):
        try:
            self.plotted_item = self.get_chosen()
            if self.plotted_item is None:
                raise ValueError
            self.plot_chosen()
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText('Choose a ROI to plot from the list!')
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    # Visualization
    def plot_current(self):
        try:
            if not self.current_flag:
                self.current_flag = True
                self.current_description = self.description
                self.plotted_roi = self.ROIs[self.file_suffix]  # 标注完成后，list index out of range：跳except弹出完成提示
                filename = f'{self.file_prefix}_{self.file_suffix}.json'
                self.plotted_path = os.path.join(self.folder, filename)

                self.figure.clear()
                ax = self.figure.add_subplot(111)
                ax.plot(self.plotted_roi.i, label=filename)
                title = f'mz = {self.plotted_roi.mzmean:.3f}, ' \
                        f'rt = {self.plotted_roi.rt[0]:.1f} - {self.plotted_roi.rt[1]:.1f}'
                ax.legend(loc='best')
                ax.set_title(title)
                self.canvas.draw()  # refresh canvas
        except IndexError:
            msg = QtWidgets.QMessageBox(self)
            msg.setText('已标注完所有ROI')
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    def plot_chosen(self):
        filename = self.plotted_item.text()
        path2roi = self.rois_list.file2path[filename]
        with open(path2roi) as json_file:
            roi = json.load(json_file)
        self.current_description = roi['description']
        self.plotted_roi = construct_ROI(roi)
        self.plotted_path = path2roi
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(self.plotted_roi.i, label=filename)
        title = f'mz = {self.plotted_roi.mzmean:.3f}, ' \
                f'rt = {self.plotted_roi.rt[0]:.1f} - {self.plotted_roi.rt[1]:.1f}'

        if roi['label'] == 0:
            title = 'label = noise, ' + title
        elif roi['label'] == 1:
            title = 'label = peak, ' + title
        else:
            title = 'label = unmarked, ' + title

        for border, peak_score in zip(roi['borders'], roi["peaks' score"]):
            begin, end = border
            if begin < 0:
                begin = 0
            ax.fill_between(range(begin, end + 1), self.plotted_roi.i[begin:end + 1], alpha=0.5,
                            label=f"score: {peak_score}, borders={begin}-{end}")

        ax.set_title(title)
        ax.legend(loc='best')
        self.canvas.draw()
        self.current_flag = False

    def plot_preview(self, borders):
        filename = os.path.basename(self.plotted_path)
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(self.plotted_roi.i, label=filename)
        title = f'mz = {self.plotted_roi.mzmean:.3f}, ' \
                f'rt = {self.plotted_roi.rt[0]:.1f} - {self.plotted_roi.rt[1]:.1f}'

        for border in borders:
            begin, end = border
            ax.fill_between(range(begin, end + 1), self.plotted_roi.i[begin:end + 1], alpha=0.5)
        ax.set_title(title)
        ax.legend(loc='best')
        self.canvas.draw()  # refresh canvas


class AnnotationGetNumberOfPeaksNovel(QtWidgets.QDialog):
    def __init__(self, parent: AnnotationMainWindow):
        self.parent = parent
        super().__init__(parent)
        self.setWindowTitle('峰个数')

        n_of_peaks_layout = QtWidgets.QHBoxLayout()
        n_of_peaks_label = QtWidgets.QLabel()
        n_of_peaks_label.setText('峰个数 = ')
        self.n_of_peaks_getter = QtWidgets.QLineEdit(self)
        self.n_of_peaks_getter.setText('2')
        n_of_peaks_layout.addWidget(n_of_peaks_label)
        n_of_peaks_layout.addWidget(self.n_of_peaks_getter)

        continue_button = QtWidgets.QPushButton('确定')
        continue_button.clicked.connect(self.proceed)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(n_of_peaks_layout)
        main_layout.addWidget(continue_button)

        self.setLayout(main_layout)

    def proceed(self):
        try:
            number_of_peaks = int(self.n_of_peaks_getter.text())
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText("请输入整数")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            return None

        subwindow = AnnotationGetBordersWindowNovel(number_of_peaks, self.parent)
        subwindow.show()
        self.close()


class OnePeakScoreWindow(QtWidgets.QDialog):
    def __init__(self, parent: AnnotationMainWindow):
        self.parent = parent
        super().__init__(parent)

        peak_score_layout = QtWidgets.QHBoxLayout()
        peak_score_label = QtWidgets.QLabel()
        peak_score_label.setText('峰形评分：')
        self.peak_score_getter = QtWidgets.QLabel(self)
        self.peak_score_getter.setText('请选择分数')
        peak_score_layout.addWidget(peak_score_label)
        peak_score_layout.addWidget(self.peak_score_getter)

        score1_btn = QtWidgets.QPushButton('1分', self)
        score1_btn.clicked.connect(lambda: self.score(1))
        score2_btn = QtWidgets.QPushButton('2分', self)
        score2_btn.clicked.connect(lambda: self.score(2))
        score3_btn = QtWidgets.QPushButton('3分', self)
        score3_btn.clicked.connect(lambda: self.score(3))
        score4_btn = QtWidgets.QPushButton('4分', self)
        score4_btn.clicked.connect(lambda: self.score(4))
        score5_btn = QtWidgets.QPushButton('5分', self)
        score5_btn.clicked.connect(lambda: self.score(5))
        score6_btn = QtWidgets.QPushButton('6分', self)
        score6_btn.clicked.connect(lambda: self.score(6))
        score7_btn = QtWidgets.QPushButton('7分', self)
        score7_btn.clicked.connect(lambda: self.score(7))
        score8_btn = QtWidgets.QPushButton('8分', self)
        score8_btn.clicked.connect(lambda: self.score(8))
        score9_btn = QtWidgets.QPushButton('9分', self)
        score9_btn.clicked.connect(lambda: self.score(9))
        score10_btn = QtWidgets.QPushButton('10分', self)
        score10_btn.clicked.connect(lambda: self.score(10))

        layout_score_row1 = QtWidgets.QHBoxLayout()
        layout_score_row2 = QtWidgets.QHBoxLayout()
        layout_score_row1.addWidget(score1_btn, 1)
        layout_score_row1.addWidget(score2_btn, 1)
        layout_score_row1.addWidget(score3_btn, 1)
        layout_score_row1.addWidget(score4_btn, 1)
        layout_score_row1.addWidget(score5_btn, 1)
        layout_score_row2.addWidget(score6_btn, 1)
        layout_score_row2.addWidget(score7_btn, 1)
        layout_score_row2.addWidget(score8_btn, 1)
        layout_score_row2.addWidget(score9_btn, 1)
        layout_score_row2.addWidget(score10_btn, 1)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(peak_score_layout)
        main_layout.addLayout(layout_score_row1)
        main_layout.addLayout(layout_score_row2)

        save_button = QtWidgets.QPushButton('保存')
        save_button.clicked.connect(self.save)
        # save_button.setShortcut(QtCore.Qt.Key_Return)  # test
        main_layout.addWidget(save_button)

        self.setLayout(main_layout)

    def score(self, n=0):
        # print(n)
        self.peak_score_getter.setNum(n)
        return n

    def save(self):
        try:
            code = os.path.basename(self.parent.plotted_path)
            with open(self.parent.plotted_path) as json_file:
                roi = json.load(json_file)
            label = roi['label']
            if self.parent.mode != 'reannotation':  # 首次标注时，获取文本框中的dropped_points
                dropped_points = self.parent.dropped_points
            else:  # 模式为继续标注时，读取文件中的dropped_points
                dropped_points = roi['drop points']

            code = code[:code.rfind('.')]
            label = 1
            borders = []
            peak_score = self.peak_score_getter.text()
            peaks_score = [peak_score]
            roi_length = self.parent.plotted_roi.scan[1] - self.parent.plotted_roi.scan[0]  # 获取ROI scan数

            begin = dropped_points - 1
            end = roi_length - dropped_points + 1  # 根据设置的最大零点数自动标记峰
            borders.append((begin, end))
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText("Check parameters. Something is wrong!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

        self.parent.plotted_roi.save_annotated(self.parent.plotted_path, code, label, 1,
                                               peaks_score, borders, description=self.parent.current_description)
        self.parent.rois_list.refresh_background(self.parent.plotted_path)  # 更新列表背景

        if self.parent.current_flag:
            self.parent.current_flag = False
            # self.parent.rois_list.addFile(self.parent.plotted_path)
            self.parent.file_suffix += 1
            self.parent.plot_current()
        else:
            self.parent.plotted_item.setSelected(False)
            index = min(self.parent.rois_list.row(self.parent.plotted_item) + 1, self.parent.rois_list.count() - 1)
            self.parent.plotted_item = self.parent.rois_list.item(index)
            self.parent.plotted_item.setSelected(True)
            self.parent.plot_chosen()
        self.close()


class AnnotationPeaksWindow(QtWidgets.QWidget):  # 多峰标注设置
    def __init__(self, peak_number, parent):
        super().__init__(parent)

        borders_layout = QtWidgets.QHBoxLayout()

        label = QtWidgets.QLabel()
        label.setText(f'Peak #{peak_number}')

        begin_label = QtWidgets.QLabel()
        begin_label.setText('begin = ')
        self.begin_getter = QtWidgets.QLineEdit(self)
        end_label = QtWidgets.QLabel()
        end_label.setText('end = ')
        self.end_getter = QtWidgets.QLineEdit(self)
        borders_layout.addWidget(begin_label)
        borders_layout.addWidget(self.begin_getter)
        borders_layout.addWidget(end_label)
        borders_layout.addWidget(self.end_getter)

        peak_score_layout = QtWidgets.QHBoxLayout()
        peak_score_label = QtWidgets.QLabel()
        peak_score_label.setText('峰形评分：')
        self.peak_score_getter = QtWidgets.QLabel(self)
        self.peak_score_getter.setText('请选择分数')
        peak_score_layout.addWidget(peak_score_label)
        peak_score_layout.addWidget(self.peak_score_getter)

        score1_btn = QtWidgets.QPushButton('1分', self)
        score1_btn.clicked.connect(lambda: self.score(1))
        score2_btn = QtWidgets.QPushButton('2分', self)
        score2_btn.clicked.connect(lambda: self.score(2))
        score3_btn = QtWidgets.QPushButton('3分', self)
        score3_btn.clicked.connect(lambda: self.score(3))
        score4_btn = QtWidgets.QPushButton('4分', self)
        score4_btn.clicked.connect(lambda: self.score(4))
        score5_btn = QtWidgets.QPushButton('5分', self)
        score5_btn.clicked.connect(lambda: self.score(5))
        score6_btn = QtWidgets.QPushButton('6分', self)
        score6_btn.clicked.connect(lambda: self.score(6))
        score7_btn = QtWidgets.QPushButton('7分', self)
        score7_btn.clicked.connect(lambda: self.score(7))
        score8_btn = QtWidgets.QPushButton('8分', self)
        score8_btn.clicked.connect(lambda: self.score(8))
        score9_btn = QtWidgets.QPushButton('9分', self)
        score9_btn.clicked.connect(lambda: self.score(9))
        score10_btn = QtWidgets.QPushButton('10分', self)
        score10_btn.clicked.connect(lambda: self.score(10))

        layout_score_row1 = QtWidgets.QHBoxLayout()
        layout_score_row2 = QtWidgets.QHBoxLayout()
        layout_score_row1.addWidget(score1_btn, 1)
        layout_score_row1.addWidget(score2_btn, 1)
        layout_score_row1.addWidget(score3_btn, 1)
        layout_score_row1.addWidget(score4_btn, 1)
        layout_score_row1.addWidget(score5_btn, 1)
        layout_score_row2.addWidget(score6_btn, 1)
        layout_score_row2.addWidget(score7_btn, 1)
        layout_score_row2.addWidget(score8_btn, 1)
        layout_score_row2.addWidget(score9_btn, 1)
        layout_score_row2.addWidget(score10_btn, 1)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(label)
        main_layout.addLayout(borders_layout)
        main_layout.addLayout(peak_score_layout)
        main_layout.addLayout(layout_score_row1)
        main_layout.addLayout(layout_score_row2)

        self.setLayout(main_layout)

    def score(self, n=0):
        # print(n)
        self.peak_score_getter.setNum(n)
        return n


class AnnotationGetBordersWindowNovel(QtWidgets.QDialog):  # 多峰标注界面
    def __init__(self, number_of_peaks: int, parent: AnnotationMainWindow):
        # self.str2label = {'': 0, '<None>': 0, 'Good (smooth, high intensive)': 1,
        #                   'Low intensive (close to LOD)': 2, 'Lousy (not good)': 3,
        #                   'Noisy, strange (probably chemical noise)': 4}
        self.number_of_peaks = number_of_peaks
        self.parent = parent
        super().__init__(parent)
        self.setWindowTitle("多峰边界标注")

        main_layout = QtWidgets.QVBoxLayout()
        self.peak_layouts = []
        for i in range(number_of_peaks):
            self.peak_layouts.append(AnnotationPeaksWindow(i + 1, self))
            main_layout.addWidget(self.peak_layouts[-1])

        preview_button = QtWidgets.QPushButton('预览')
        preview_button.clicked.connect(self.preview)
        main_layout.addWidget(preview_button)

        save_button = QtWidgets.QPushButton('保存')
        save_button.clicked.connect(self.save)
        main_layout.addWidget(save_button)

        self.setLayout(main_layout)

    def preview(self):
        try:
            borders = []
            for ps in self.peak_layouts:
                if ps.begin_getter.text() and ps.end_getter.text():
                    begin = ps.begin_getter.text()
                    end = ps.end_getter.text()
                    if begin and end:
                        begin = int(begin)
                        end = int(end)
                        borders.append((begin, end))
            self.parent.plot_preview(borders)
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText("始末点应为横坐标范围内整数")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    def save(self):
        try:
            code = os.path.basename(self.parent.plotted_path)
            code = code[:code.rfind('.')]
            label = 1
            number_of_peaks = self.number_of_peaks
            peaks_score = []
            borders = []
            for ps in self.peak_layouts:
                peak_score = ps.peak_score_getter.text()
                peaks_score.append(peak_score)

                begin = int(ps.begin_getter.text())
                end = int(ps.end_getter.text())
                borders.append((begin, end))
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText("始末点应为横坐标范围内整数")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

        self.parent.plotted_roi.save_annotated(self.parent.plotted_path, code, label, number_of_peaks,
                                               peaks_score, borders, description=self.parent.current_description)
        self.parent.rois_list.refresh_background(self.parent.plotted_path)  # 更新列表背景

        if self.parent.current_flag:
            self.parent.current_flag = False
            self.parent.rois_list.addFile(self.parent.plotted_path)
            self.parent.file_suffix += 1
            self.parent.plot_current()
        else:
            self.parent.plotted_item.setSelected(False)
            index = min(self.parent.rois_list.row(self.parent.plotted_item) + 1, self.parent.rois_list.count() - 1)
            self.parent.plotted_item = self.parent.rois_list.item(index)
            self.parent.plotted_item.setSelected(True)
            self.parent.plot_chosen()
        self.close()


class FileContextMenu(QtWidgets.QMenu):
    def __init__(self, parent: AnnotationMainWindow):
        super().__init__(parent)

        self.parent = parent
        self.menu = QtWidgets.QMenu(parent)

        # self.reannotation = QtWidgets.QAction('reannotation', parent)
        self.close = QtWidgets.QAction('Close', parent)
        self.delete = QtWidgets.QAction('Delete', parent)

        # self.menu.addAction(self.reannotation)
        self.menu.addAction(self.close)
        self.menu.addAction(self.delete)

        action = self.menu.exec_(QtGui.QCursor.pos())

        if action == self.close:
            self.close_file()
        elif action == self.delete:
            self.delete_file()
        # elif action == self.reannotation:
        #     self.reannotation()

    def close_file(self):
        item = self.parent.get_chosen()
        self.parent.close_file(item)

    def delete_file(self):
        item = self.parent.get_chosen()
        self.parent.delete_file(item)
