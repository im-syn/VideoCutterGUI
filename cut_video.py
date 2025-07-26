#!/usr/bin/env python3
"""
Professional Video Cutter Tool
A modern GUI application for splitting videos into smaller segments.
"""

import os
import sys
import math
import subprocess
import threading
import time
from pathlib import Path
from datetime import timedelta

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QProgressBar,
    QSpinBox, QGroupBox, QGridLayout, QTextEdit, QFrame,
    QSizePolicy, QComboBox, QCheckBox, QScrollArea
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor, QIcon, QPainter, QLinearGradient
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize

class VideoSplitterWorker(QThread):
    """Worker thread for video splitting operations."""
    progress_updated = pyqtSignal(int)  # Progress percentage
    status_updated = pyqtSignal(str)    # Status message
    log_updated = pyqtSignal(str)       # Log message
    finished = pyqtSignal(bool, str)    # Success, message
    segment_completed = pyqtSignal(str, int)  # Segment path, segment number
    
    def __init__(self, video_path, output_dir, segment_minutes, segment_seconds, keep_audio=True, quality="high"):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.segment_duration = segment_minutes * 60 + segment_seconds  # Convert to total seconds
        self.keep_audio = keep_audio
        self.quality = quality
        self.is_running = True
        
    def run(self):
        try:
            self.status_updated.emit("Analyzing video...")
            self.log_updated.emit(f"Starting video split: {os.path.basename(self.video_path)}")
            
            # Get video duration
            duration = self.get_video_duration()
            if duration <= 0:
                self.finished.emit(False, "Could not determine video duration")
                return
                
            total_segments = math.ceil(duration / self.segment_duration)
            self.log_updated.emit(f"Video duration: {self.seconds_to_time(duration)}")
            self.log_updated.emit(f"Segment duration: {self.seconds_to_time(self.segment_duration)}")
            self.log_updated.emit(f"Total segments to create: {total_segments}")
            
            # Create output directory
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Split video into segments
            video_name = Path(self.video_path).stem
            successful_segments = 0
            
            for i in range(total_segments):
                if not self.is_running:
                    break
                    
                start_time = i * self.segment_duration
                segment_num = i + 1
                
                # Calculate end time (don't exceed video duration)
                end_time = min(start_time + self.segment_duration, duration)
                actual_duration = end_time - start_time
                
                if actual_duration <= 1:  # Skip segments shorter than 1 second
                    continue
                
                self.status_updated.emit(f"Creating segment {segment_num}/{total_segments}...")
                self.log_updated.emit(f"Processing segment {segment_num}: {self.seconds_to_time(start_time)} - {self.seconds_to_time(end_time)}")
                
                # Create output filename
                output_filename = f"{video_name}_part_{segment_num:03d}.mp4"
                output_path = os.path.join(self.output_dir, output_filename)
                
                # Split the segment
                success = self.split_segment(start_time, actual_duration, output_path)
                
                if success:
                    successful_segments += 1
                    self.segment_completed.emit(output_path, segment_num)
                    self.log_updated.emit(f"✅ Segment {segment_num} completed: {output_filename}")
                else:
                    self.log_updated.emit(f"❌ Failed to create segment {segment_num}")
                
                # Update progress
                progress = int((segment_num / total_segments) * 100)
                self.progress_updated.emit(progress)
                
            if self.is_running:
                if successful_segments > 0:
                    self.log_updated.emit(f"🎉 Successfully created {successful_segments} segments")
                    self.finished.emit(True, f"Successfully split video into {successful_segments} segments")
                else:
                    self.finished.emit(False, "No segments were created successfully")
            else:
                self.finished.emit(False, "Operation cancelled by user")
                
        except Exception as e:
            self.log_updated.emit(f"❌ Error: {str(e)}")
            self.finished.emit(False, f"Error: {str(e)}")
    
    def get_video_duration(self):
        """Get video duration in seconds using ffprobe."""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', self.video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                return duration
            else:
                # Fallback method using ffmpeg
                return self.get_duration_fallback()
                
        except Exception as e:
            self.log_updated.emit(f"Warning: Could not get precise duration: {e}")
            return self.get_duration_fallback()
    
    def get_duration_fallback(self):
        """Fallback method to get video duration."""
        try:
            cmd = [
                'ffmpeg', '-i', self.video_path, '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = result.stderr
            
            # Parse duration from ffmpeg output
            for line in output.split('\n'):
                if 'Duration:' in line:
                    duration_str = line.split('Duration:')[1].split(',')[0].strip()
                    return self.time_to_seconds(duration_str)
                    
            return 0
        except:
            return 0
    
    def split_segment(self, start_time, duration, output_path):
        """Split a single segment from the video."""
        try:
            # Build ffmpeg command
            cmd = ['ffmpeg', '-y']  # -y to overwrite existing files
            
            # Input file with start time
            cmd.extend(['-ss', str(start_time)])
            cmd.extend(['-i', self.video_path])
            
            # Duration
            cmd.extend(['-t', str(duration)])
            
            # Quality settings
            if self.quality == "high":
                cmd.extend(['-c:v', 'libx264', '-crf', '18'])
            elif self.quality == "medium":
                cmd.extend(['-c:v', 'libx264', '-crf', '23'])
            else:  # low
                cmd.extend(['-c:v', 'libx264', '-crf', '28'])
            
            # Audio settings
            if self.keep_audio:
                cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
            else:
                cmd.extend(['-an'])  # No audio
            
            # Other settings
            cmd.extend(['-avoid_negative_ts', 'make_zero'])
            cmd.extend(['-movflags', '+faststart'])
            
            # Output file
            cmd.append(output_path)
            
            # Run ffmpeg
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minute timeout per segment
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            return result.returncode == 0 and os.path.exists(output_path)
            
        except subprocess.TimeoutExpired:
            self.log_updated.emit("⚠️ Segment processing timed out")
            return False
        except Exception as e:
            self.log_updated.emit(f"⚠️ Error processing segment: {e}")
            return False
    
    def time_to_seconds(self, time_str):
        """Convert time string (HH:MM:SS.ms) to seconds."""
        try:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except:
            return 0
    
    def seconds_to_time(self, seconds):
        """Convert seconds to time string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def stop(self):
        """Stop the splitting process."""
        self.is_running = False

class ModernDropArea(QLabel):
    """Modern drag and drop area for video files."""
    file_dropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setText("🎬 Drag & Drop Video File Here\n\nOr Click to Browse\n\n✨ Supported: MP4, AVI, MOV, MKV, WMV ✨")
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(150)
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #667eea;
                border-radius: 12px;
                padding: 30px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #f8f9fa, stop:1 #e9ecef);
                font-size: 16px;
                font-weight: bold;
                color: #495057;
            }
        """)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet("""
                QLabel {
                    border: 3px dashed #5a6fd8;
                    border-radius: 12px;
                    padding: 30px;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                              stop:0 #e8ecf7, stop:1 #d1d9f4);
                    font-size: 16px;
                    font-weight: bold;
                    color: #495057;
                }
            """)
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #667eea;
                border-radius: 12px;
                padding: 30px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #f8f9fa, stop:1 #e9ecef);
                font-size: 16px;
                font-weight: bold;
                color: #495057;
            }
        """)
        
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            if self.is_video_file(file_path):
                self.file_dropped.emit(file_path)
            else:
                QMessageBox.warning(self, "Invalid File", "Please select a valid video file!")
        
        self.dragLeaveEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.browse_file()
    
    def browse_file(self):
        """Open file dialog to browse for video file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm);;All Files (*)"
        )
        if file_path:
            self.file_dropped.emit(file_path)
    
    def is_video_file(self, file_path):
        """Check if file is a video file."""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        return Path(file_path).suffix.lower() in video_extensions

class ModernProgressBar(QWidget):
    """Modern animated progress bar."""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.progress = 0
        self.text = "Ready"
        self.is_animated = False
        
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 20px;
            }
        """)
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        
    def set_progress(self, value, text=""):
        """Set progress value and text."""
        self.progress = max(0, min(100, value))
        if text:
            self.text = text
        self.update()
        
    def start_animation(self, text="Processing..."):
        """Start progress animation."""
        self.text = text
        self.is_animated = True
        self.timer.start(100)
        
    def stop_animation(self):
        """Stop progress animation."""
        self.is_animated = False
        self.timer.stop()
        
    def paintEvent(self, event):
        """Custom paint event for modern progress bar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # Background
        painter.fillRect(rect, QColor("#2b2b2b"))
        
        # Progress bar
        if self.progress > 0:
            progress_width = int((rect.width() - 4) * self.progress / 100)
            progress_rect = rect.adjusted(2, 2, 2 - rect.width() + progress_width + 2, -2)
            
            # Gradient for progress
            gradient = QLinearGradient(0, 0, progress_width, 0)
            gradient.setColorAt(0, QColor("#667eea"))
            gradient.setColorAt(1, QColor("#764ba2"))
            painter.fillRect(progress_rect, gradient)
        
        # Text
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        text_to_show = f"{self.text} ({self.progress}%)" if self.progress > 0 else self.text
        painter.drawText(rect, Qt.AlignCenter, text_to_show)

class SegmentPreviewWidget(QWidget):
    """Widget to preview created segments."""
    def __init__(self):
        super().__init__()
        self.segments = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("📁 Created Segments")
        header.setFont(QFont("Arial", 14, QFont.Bold))
        header.setStyleSheet("color: #495057; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Scroll area for segments
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # Empty state
        self.empty_label = QLabel("No segments created yet...")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 14px;
                padding: 20px;
                font-style: italic;
            }
        """)
        self.scroll_layout.addWidget(self.empty_label)
        
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)
        
    def add_segment(self, segment_path, segment_number):
        """Add a segment to the preview."""
        if self.empty_label.parent():
            self.empty_label.setParent(None)
        
        segment_widget = QWidget()
        segment_widget.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin: 2px;
                padding: 8px;
            }
            QWidget:hover {
                border-color: #667eea;
                background-color: #f8f9ff;
            }
        """)
        
        layout = QHBoxLayout(segment_widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Segment info
        filename = os.path.basename(segment_path)
        file_size = os.path.getsize(segment_path) / (1024 * 1024) if os.path.exists(segment_path) else 0
        
        info_label = QLabel(f"🎬 {filename}\n📊 {file_size:.1f} MB")
        info_label.setStyleSheet("color: #495057; font-size: 12px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Play button
        play_btn = QPushButton("▶️ Play")
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        play_btn.clicked.connect(lambda: self.play_segment(segment_path))
        layout.addWidget(play_btn)
        
        self.scroll_layout.addWidget(segment_widget)
        self.segments.append(segment_path)
        
        # Scroll to show latest segment
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))
    
    def play_segment(self, segment_path):
        """Play a segment using the default system player."""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(segment_path)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', segment_path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open video player:\n{e}")
    
    def clear_segments(self):
        """Clear all segments."""
        for i in reversed(range(self.scroll_layout.count())):
            child = self.scroll_layout.itemAt(i).widget()
            if child and child != self.empty_label:
                child.setParent(None)
        
        self.segments.clear()
        self.scroll_layout.addWidget(self.empty_label)

class VideoCutterGUI(QMainWindow):
    """Main GUI window for Video Cutter application."""
    
    def __init__(self):
        super().__init__()
        self.current_video = None
        self.worker = None
        self.output_directory = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("🎬 SYN Video Cutter v1.0")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        # Set modern theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }
            QPushButton {
                background-color: #667eea;
                color: white;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #5a6fd8;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #adb5bd;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Left panel - Controls
        left_panel = self.create_control_panel()
        content_layout.addWidget(left_panel, 1)
        
        # Right panel - Preview and output
        right_panel = self.create_preview_panel()
        content_layout.addWidget(right_panel, 1)
        
        main_layout.addLayout(content_layout)
        
        # Status bar
        self.create_status_bar()
        
    def create_header(self):
        """Create the header section."""
        header_widget = QWidget()
        header_widget.setFixedHeight(120)
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                          stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
                border: 2px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(header_widget)
        layout.setContentsMargins(30, 15, 30, 15)
        layout.setSpacing(8)
        
        # Top row - Title and GitHub
        top_row = QHBoxLayout()
        
        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(5)
        
        title = QLabel("🎬 SYN Video Cutter")
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setStyleSheet("color: white; border: none;")
        title_section.addWidget(title)
        
        subtitle = QLabel("✨ Split videos into smaller segments with precision ✨")
        subtitle.setFont(QFont("Arial", 13))
        subtitle.setStyleSheet("color: #e8ecf7; border: none; font-style: italic;")
        title_section.addWidget(subtitle)
        
        top_row.addLayout(title_section)
        top_row.addStretch()
        
        # GitHub section
        github_section = QVBoxLayout()
        github_section.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        github_section.setSpacing(5)
        
        # GitHub button
        github_btn = QPushButton("⭐ GitHub - SYN")
        github_btn.setFont(QFont("Arial", 12, QFont.Bold))
        github_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 20px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-2px);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        github_btn.clicked.connect(self.open_github)
        github_section.addWidget(github_btn)
        
        # Support message
        support_label = QLabel("💝 Support the Developer")
        support_label.setFont(QFont("Arial", 10))
        support_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); border: none;")
        support_label.setAlignment(Qt.AlignCenter)
        github_section.addWidget(support_label)
        
        top_row.addLayout(github_section)
        
        layout.addLayout(top_row)
        
        # Bottom decorative line
        line = QLabel()
        line.setFixedHeight(2)
        line.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                          stop:0 rgba(255,255,255,0.3), 
                                          stop:0.5 rgba(255,255,255,0.6), 
                                          stop:1 rgba(255,255,255,0.3));
                border-radius: 1px;
                margin: 5px 20px;
            }
        """)
        layout.addWidget(line)
        
        return header_widget
    
    def create_control_panel(self):
        """Create the control panel."""
        panel = QWidget()
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)
        
        # File input section
        file_group = QGroupBox("📁 Video Input")
        file_layout = QVBoxLayout(file_group)
        
        self.drop_area = ModernDropArea()
        self.drop_area.file_dropped.connect(self.load_video)
        file_layout.addWidget(self.drop_area)
        
        # Current file info
        self.file_info_label = QLabel("No file selected")
        self.file_info_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 12px;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #dee2e6;
            }
        """)
        file_layout.addWidget(self.file_info_label)
        
        layout.addWidget(file_group)
        
        # Settings section
        settings_group = QGroupBox("⚙️ Split Settings")
        settings_layout = QGridLayout(settings_group)
        
        # Segment duration
        settings_layout.addWidget(QLabel("Segment Duration:"), 0, 0)
        
        duration_layout = QHBoxLayout()
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 999)
        self.minutes_spin.setValue(2)
        self.minutes_spin.setSuffix(" min")
        duration_layout.addWidget(self.minutes_spin)
        
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setRange(0, 59)
        self.seconds_spin.setValue(20)
        self.seconds_spin.setSuffix(" sec")
        duration_layout.addWidget(self.seconds_spin)
        
        duration_widget = QWidget()
        duration_widget.setLayout(duration_layout)
        settings_layout.addWidget(duration_widget, 0, 1)
        
        # Quality settings
        settings_layout.addWidget(QLabel("Video Quality:"), 1, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["High (Best)", "Medium (Balanced)", "Low (Smaller files)"])
        self.quality_combo.setCurrentText("High (Best)")
        settings_layout.addWidget(self.quality_combo, 1, 1)
        
        # Audio settings
        self.keep_audio_check = QCheckBox("Keep Original Audio")
        self.keep_audio_check.setChecked(True)
        settings_layout.addWidget(self.keep_audio_check, 2, 0, 1, 2)
        
        # Output directory
        settings_layout.addWidget(QLabel("Output Directory:"), 3, 0)
        output_layout = QHBoxLayout()
        
        self.output_dir_label = QLabel("Same as input video")
        self.output_dir_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        output_layout.addWidget(self.output_dir_label)
        
        browse_output_btn = QPushButton("📁")
        browse_output_btn.setMaximumWidth(40)
        browse_output_btn.clicked.connect(self.browse_output_directory)
        output_layout.addWidget(browse_output_btn)
        
        output_widget = QWidget()
        output_widget.setLayout(output_layout)
        settings_layout.addWidget(output_widget, 3, 1)
        
        layout.addWidget(settings_group)
        
        # Process section
        process_group = QGroupBox("🚀 Processing")
        process_layout = QVBoxLayout(process_group)
        
        self.start_button = QPushButton("✂️ Start Cutting Video")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_cutting)
        process_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹️ Stop Process")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_cutting)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        process_layout.addWidget(self.stop_button)
        
        # Progress bar
        self.progress_bar = ModernProgressBar()
        process_layout.addWidget(self.progress_bar)
        
        layout.addWidget(process_group)
        
        layout.addStretch()
        return panel
    
    def create_preview_panel(self):
        """Create the preview and output panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Log section
        log_group = QGroupBox("📋 Processing Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        # Clear log button
        clear_log_btn = QPushButton("🗑️ Clear Log")
        clear_log_btn.setMaximumWidth(120)
        clear_log_btn.clicked.connect(self.log_text.clear)
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        
        # Segments preview
        segments_group = QGroupBox("🎬 Output Segments")
        segments_layout = QVBoxLayout(segments_group)
        
        self.segments_preview = SegmentPreviewWidget()
        segments_layout.addWidget(self.segments_preview)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        
        self.open_folder_btn = QPushButton("📂 Open Output Folder")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        actions_layout.addWidget(self.open_folder_btn)
        
        self.clear_segments_btn = QPushButton("🗑️ Clear Segments")
        self.clear_segments_btn.clicked.connect(self.clear_segments)
        self.clear_segments_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        actions_layout.addWidget(self.clear_segments_btn)
        
        segments_layout.addLayout(actions_layout)
        
        layout.addWidget(segments_group)
        
        return panel
    
    def create_status_bar(self):
        """Create status bar."""
        status_bar = self.statusBar()
        status_bar.showMessage("Ready - Select a video file to begin")
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #e9ecef;
                color: #495057;
                border-top: 1px solid #dee2e6;
                padding: 5px;
            }
        """)
    
    def load_video(self, video_path):
        """Load a video file."""
        try:
            if not os.path.exists(video_path):
                QMessageBox.warning(self, "Error", "Video file does not exist!")
                return
            
            self.current_video = video_path
            filename = os.path.basename(video_path)
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            
            self.file_info_label.setText(f"📹 {filename}\n📊 Size: {file_size:.1f} MB")
            self.start_button.setEnabled(True)
            
            # Set default output directory
            if not self.output_directory:
                self.output_directory = os.path.join(os.path.dirname(video_path), "video_segments")
                self.output_dir_label.setText(f"📁 {os.path.basename(self.output_directory)}/")
            
            self.statusBar().showMessage(f"Video loaded: {filename}")
            self.log_text.append(f"✅ Video loaded: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video:\n{str(e)}")
    
    def browse_output_directory(self):
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory",
            os.path.dirname(self.current_video) if self.current_video else ""
        )
        if directory:
            self.output_directory = directory
            self.output_dir_label.setText(f"📁 {os.path.basename(directory)}/")
    
    def start_cutting(self):
        """Start the video cutting process."""
        if not self.current_video:
            QMessageBox.warning(self, "Error", "Please select a video file first!")
            return
        
        # Check if FFmpeg is available
        if not self.check_ffmpeg():
            QMessageBox.critical(
                self, "FFmpeg Required",
                "FFmpeg is required for video processing.\n\n"
                "Please install FFmpeg and make sure it's in your system PATH.\n"
                "You can download it from: https://ffmpeg.org/download.html"
            )
            return
        
        # Get settings
        minutes = self.minutes_spin.value()
        seconds = self.seconds_spin.value()
        
        if minutes == 0 and seconds == 0:
            QMessageBox.warning(self, "Error", "Segment duration must be greater than 0!")
            return
        
        quality_map = {
            "High (Best)": "high",
            "Medium (Balanced)": "medium", 
            "Low (Smaller files)": "low"
        }
        quality = quality_map[self.quality_combo.currentText()]
        keep_audio = self.keep_audio_check.isChecked()
        
        # Use output directory or create default
        output_dir = self.output_directory or os.path.join(
            os.path.dirname(self.current_video), "video_segments"
        )
        
        # Update UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.open_folder_btn.setEnabled(False)
        self.progress_bar.start_animation("Initializing...")
        
        # Start worker thread
        self.worker = VideoSplitterWorker(
            self.current_video, output_dir, minutes, seconds, keep_audio, quality
        )
        self.worker.progress_updated.connect(self.progress_bar.set_progress)
        self.worker.status_updated.connect(self.progress_bar.start_animation)
        self.worker.log_updated.connect(self.log_text.append)
        self.worker.segment_completed.connect(self.segments_preview.add_segment)
        self.worker.finished.connect(self.cutting_finished)
        self.worker.start()
        
        self.statusBar().showMessage("Processing video...")
    
    def stop_cutting(self):
        """Stop the cutting process."""
        if self.worker:
            self.worker.stop()
            self.log_text.append("🛑 Stopping process...")
    
    def cutting_finished(self, success, message):
        """Handle cutting completion."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.stop_animation()
        
        if success:
            self.progress_bar.set_progress(100, "Completed!")
            self.open_folder_btn.setEnabled(True)
            self.statusBar().showMessage("Video cutting completed successfully!")
            QMessageBox.information(self, "Success", message)
        else:
            self.progress_bar.set_progress(0, "Failed")
            self.statusBar().showMessage("Video cutting failed!")
            QMessageBox.warning(self, "Error", message)
        
        self.worker = None
    
    def open_output_folder(self):
        """Open the output folder in file explorer."""
        if self.output_directory and os.path.exists(self.output_directory):
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(self.output_directory)
                elif os.name == 'posix':  # macOS and Linux
                    subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', self.output_directory])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")
        else:
            QMessageBox.warning(self, "Error", "Output folder does not exist!")
    
    def open_github(self):
        """Open SYN's GitHub page in the default browser."""
        try:
            import webbrowser
            webbrowser.open("https://github.com/im-syn/")
        except Exception as e:
            QMessageBox.information(
                self, "GitHub", 
                "Visit SYN's GitHub page:\nhttps://github.com/im-syn/\n\n⭐ Please star the repository if you find this tool useful!"
            )
    
    def clear_segments(self):
        """Clear all segments from preview."""
        self.segments_preview.clear_segments()
        self.log_text.append("🗑️ Segments preview cleared")
    
    def check_ffmpeg(self):
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return result.returncode == 0
        except:
            return False
    
    def closeEvent(self, event):
        """Handle application close."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "Video processing is in progress. Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait(3000)  # Wait up to 3 seconds
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("SYN Video Cutter")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("SYN Development")
    
    # Create and show main window
    window = VideoCutterGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
