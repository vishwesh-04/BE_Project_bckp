from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QLineEdit, QPushButton, QMessageBox, QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QPixmap

from client.inference_engine import PredictionResult


class InferenceTab(QWidget):
    """
    Tab 1 — Live Prediction & SHAP Explanation
      - Left 1/3: Ad-hoc prediction card (3 inputs + Run button + result card)
      - Right 2/3: SHAP Explanation card (Plot image area + Explanation text area)
    """

    # Signal to request a prediction from the worker
    predict_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        root = QHBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)

        # Left: Ad-hoc prediction card (stretch=1)
        root.addWidget(self._build_prediction_card(), stretch=1)

        # Right: SHAP Explanation card (stretch=2)
        root.addWidget(self._build_shap_card(), stretch=2)

    # -------------------------------------------------------------------- #
    #  Left column — Ad-hoc Prediction                                     #
    # -------------------------------------------------------------------- #
    def _build_prediction_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title_row = QHBoxLayout()
        title = QLabel("Ad-hoc Prediction")
        title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #1e293b; letter-spacing: 0.5px; border: none;"
        )
        title_row.addWidget(title)
        layout.addLayout(title_row)

        # Three inputs
        self._inputs = {}
        fields = [
            ("glucose", "Serum Glucose", "120"),
            ("age", "Patient Age", "45"),
            ("bmi", "Body Mass Index", "24.2"),
        ]
        for key, label_text, placeholder in fields:
            lbl = QLabel(label_text.upper())
            lbl.setStyleSheet(
                "color: #94a3b8; font-size: 9px; font-weight: 800; "
                "letter-spacing: 1px; border: none;"
            )
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            edit.setProperty("class", "EnvInput")
            edit.setFixedHeight(36)
            layout.addWidget(lbl)
            layout.addWidget(edit)
            self._inputs[key] = edit

        # Run button
        self._run_btn = QPushButton("PREDICT")
        self._run_btn.setProperty("class", "PrimaryButton")
        self._run_btn.setFixedHeight(42)
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setStyleSheet(
            "background-color: #1e293b; color: white; font-weight: 800; "
            "font-size: 10px; letter-spacing: 1px; border-radius: 10px; "
            "border: none;"
        )
        self._run_btn.clicked.connect(self._emit_predict)
        layout.addWidget(self._run_btn)

        # Result card (hidden until result)
        self._result_card = QFrame()
        self._result_card.setObjectName("ResultCard")
        self._result_card.hide()
        rc_layout = QVBoxLayout(self._result_card)
        rc_layout.setContentsMargins(20, 16, 20, 16)
        rc_layout.setSpacing(4)

        score_row = QHBoxLayout()
        self._score_text_label = QLabel("RESULT SCORE")
        self._score_text_label.setStyleSheet(
            "font-size: 9px; font-weight: 800; color: #0f766e; letter-spacing: 1px; border: none;"
        )
        self._score_lbl = QLabel("0.0%")
        self._score_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 900; color: #134e4a; border: none;"
        )
        score_row.addWidget(self._score_text_label)
        score_row.addStretch()
        score_row.addWidget(self._score_lbl)

        self._risk_lbl = QLabel("NEGATIVE / LOW RISK BASELINE")
        self._risk_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 800; color: #0f766e; letter-spacing: 0.5px; border: none;"
        )

        rc_layout.addLayout(score_row)
        rc_layout.addWidget(self._risk_lbl)

        self._result_card.setStyleSheet(
            "background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 12px;"
        )
        layout.addWidget(self._result_card)
        layout.addStretch()

        return card

    # -------------------------------------------------------------------- #
    #  Right column — SHAP Explanations                                    #
    # -------------------------------------------------------------------- #
    def _build_shap_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        card.setProperty("class", "GlassCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Card header
        header = QFrame()
        header.setStyleSheet(
            "background: #f8fafc; border-bottom: 1px solid #f1f5f9; "
            "border-top-left-radius: 12px; border-top-right-radius: 12px;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 12)

        h_title = QLabel("MODEL EXPLAINABILITY (SHAP)")
        h_title.setStyleSheet(
            "color: #64748b; font-size: 10px; font-weight: 800; "
            "letter-spacing: 1px; background: transparent; border: none;"
        )
        h_layout.addWidget(h_title)
        h_layout.addStretch()
        layout.addWidget(header)

        # Content area for SHAP
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        # 1. SHAP Plot Placeholder
        self._shap_plot_lbl = QLabel("Awaiting prediction to generate SHAP plot...")
        self._shap_plot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._shap_plot_lbl.setStyleSheet(
            "background: #f1f5f9; color: #94a3b8; font-size: 12px; "
            "border: 1px dashed #cbd5e1; border-radius: 8px;"
        )
        self._shap_plot_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Assuming the plot will take up most of the vertical space
        content_layout.addWidget(self._shap_plot_lbl, stretch=3)

        # 2. SHAP Text Explanation
        self._shap_explanation_text = QTextEdit()
        self._shap_explanation_text.setReadOnly(True)
        self._shap_explanation_text.setPlaceholderText("SHAP feature contribution explanation will appear here.")
        self._shap_explanation_text.setStyleSheet(
            "background: transparent; color: #334155; font-size: 12px; "
            "border: none;"
        )
        # Give the text area a bit less stretch than the plot
        content_layout.addWidget(self._shap_explanation_text, stretch=1)

        layout.addWidget(content_frame)
        return card

    # -------------------------------------------------------------------- #
    #  Prediction & UI Updates                                             #
    # -------------------------------------------------------------------- #
    def _emit_predict(self):
        try:
            val_map = {
                "glucose": float(self._inputs["glucose"].text() or 0.0),
                "age": float(self._inputs["age"].text() or 0.0),
                "bmi": float(self._inputs["bmi"].text() or 0.0),
            }
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers.")
            return

        self._run_btn.setText("PREDICTING…")
        self._run_btn.setEnabled(False)

        # Reset SHAP UI while predicting
        self._shap_plot_lbl.setText("Generating SHAP plot...")
        self._shap_plot_lbl.setPixmap(QPixmap())
        self._shap_explanation_text.clear()

        self.predict_requested.emit(val_map)

    @Slot(object)
    def display_prediction_result(self, result):
        self._run_btn.setText("PREDICT")
        self._run_btn.setEnabled(True)

        if isinstance(result, Exception):
            QMessageBox.critical(self, "Prediction Error", str(result))
            self._shap_plot_lbl.setText("Error generating SHAP explanation.")
            return

        res: PredictionResult = result
        score = f"{res.probability:.1%}"
        is_high = res.risk_label != "Low"

        self._score_lbl.setText(score)
        self._result_card.show()

        if is_high:
            self._result_card.setStyleSheet(
                "background: #fff1f2; border: 1px solid #fecdd3; border-radius: 12px;"
            )
            self._score_text_label.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #be123c; letter-spacing: 1px; border: none;"
            )
            self._score_lbl.setStyleSheet(
                "font-size: 18px; font-weight: 900; color: #9f1239; border: none;"
            )
            self._risk_lbl.setText("POSITIVE / HIGH RISK — REVIEW REQUIRED")
            self._risk_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #be123c; letter-spacing: 0.5px; border: none;"
            )
        else:
            self._result_card.setStyleSheet(
                "background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 12px;"
            )
            self._score_text_label.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #0f766e; letter-spacing: 1px; border: none;"
            )
            self._score_lbl.setStyleSheet(
                "font-size: 18px; font-weight: 900; color: #134e4a; border: none;"
            )
            self._risk_lbl.setText("NEGATIVE / LOW RISK BASELINE")
            self._risk_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #0f766e; letter-spacing: 0.5px; border: none;"
            )

    @Slot(QPixmap, str)
    def display_shap_result(self, pixmap: QPixmap, explanation: str):
        """
        Call this method from your main window/controller once the SHAP
        plot and explanation text are ready.
        """
        if not pixmap.isNull():
            # Scale the pixmap to fit the label while keeping aspect ratio
            scaled_pixmap = pixmap.scaled(
                self._shap_plot_lbl.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._shap_plot_lbl.setPixmap(scaled_pixmap)
        else:
            self._shap_plot_lbl.setText("Failed to load SHAP plot.")

        self._shap_explanation_text.setText(explanation)