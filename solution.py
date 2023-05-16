# -*- coding: utf-8 -*-
"""
@author: j.
"""

import logging
logging.basicConfig(
    level=logging.INFO,  # Set the desired logging level 
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('./application.log'),  # Log to a file
        logging.StreamHandler()  # Log to console
    ]
)

import os
import sys
import pandas as pd

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QListWidget, QSplitter, QApplication, QMainWindow, 
    QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLineEdit, 
    QWidget, QPushButton, QTableWidget, QListWidgetItem,
    QTableWidgetItem, QLabel, QAbstractItemView, QStyledItemDelegate, QDialog
)

from PySide6.QtGui import (
    QTextCharFormat, QColor, QFont, QPalette
)

from document_processor import ( AppCoordinator, AppSettings )



class MainWindow(QMainWindow):
    def __init__(self, coordinator):
        super().__init__()
        self.app_status = 'OFFLINE'
        
        # the app needs these things to work but should stop asking for them once we see them set to true
        self.api_key_valid = False
        self.has_embeddings = False
        
        # main functions of the app happen in this class
        self.coordinator = coordinator
        
        self.setWindowTitle("RAGing Knowledge (Retrieval Augmented Generation)")
        self.setGeometry(250, 250, 800, 600)
        
        # .txt documents go here
        documents_folder = './documents'
        
        # create the empty folder on first run 
        if not os.path.exists(documents_folder):
            os.makedirs(documents_folder)
        
        self.init_ui()
        self.startup_check()

    def startup_check(self):
        if not self.api_key_valid:
            self.api_key_valid = self.coordinator.api_key_valid()
            
            if not self.api_key_valid:
                self.update_progress("INVALID API KEY. Close the application and add your API key to api_key.txt. Then try again.")
                self.app_status = 'OFFLINE'
                self.send_button.setEnabled(False)
                self.settings_link.setEnabled(False)
                return
        
        if not self.has_embeddings:
            self.has_embeddings = self.coordinator.get_embedding_status()
            
            if not self.has_embeddings:
                self.update_progress("NO EMBEDDINGS FOUND. Please add your documents, then create the document embeddings (click the Settings button).")
                self.app_status = 'OFFLINE'
                self.send_button.setEnabled(False)
                self.settings_link.setEnabled(True) # settings button should be on now!
                return
        
        self.update_progress("Idle")
        self.app_status = 'ONLINE'
        
        self.send_button.setEnabled(True)
        self.settings_link.setEnabled(True)


    def init_ui(self):
        # self.showMaximized()

        layout = QVBoxLayout()

        # Create a QSplitter to manage the question list and text area
        splitter = QSplitter(Qt.Horizontal)

        # Add question list on the left
        self.question_list = QListWidget()
        self.question_list.itemClicked.connect(self.handle_item_clicked)
        splitter.addWidget(self.question_list)

        # Add text area in the middle
        self.answer_area = QPlainTextEdit()
        self.answer_area.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.answer_area.setReadOnly(True)
        splitter.addWidget(self.answer_area)

        # Set stretch factors
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, stretch=3)

        # Add horizontal layout for input field and send button
        input_layout = QHBoxLayout()
        self.user_query_input = QLineEdit()
        self.user_query_input.setPlaceholderText("Ask a question..")
        input_layout.addWidget(self.user_query_input)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_question)
        input_layout.addWidget(self.send_button)
        layout.addLayout(input_layout)

        self.settings_link = QPushButton("Settings")
        self.settings_link.clicked.connect(self.show_settings_window)
        layout.addWidget(self.settings_link)
        
        # add the status label
        self.progress_label = QLabel()
        layout.addWidget(self.progress_label)
        
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # finally load up the chat history
        self.update_chat_history()
        
    
    def update_progress(self, value, color = 1):
        color_dict = {
            0: 'gray',
            1: 'black',
            2: 'green'
        }
        
        status_color = color_dict[color] if color in color_dict else color_dict[0]
        
        self.progress_label.setText(f"<b><font color='gray'>Status:  </font><font color='{status_color}'>{value}</font></b>")
        QApplication.processEvents()
    
    def send_question(self):
        # get the user query and response
        user_query = self.user_query_input.text()
        
        # do nothing if there is no question
        if len(user_query) == 0:
            return
        
        # get the answer to the question
        (question, article, answer, results_json) = self.coordinator.ask_question(user_query, self.update_progress)
        
        # update the text area with the answer content
        self.update_answer_area(question, article, answer, results_json)
        
        # save the chat to history
        self.coordinator.save_chat(question, article, answer, results_json)
        
        # update the history on UI with the latest history
        self.update_chat_history()
        
        self.update_progress("Idle")
    
    def update_chat_history(self):
        # Add the chat log objects to the list widget
        self.question_list.clear()
        
        for chat_data in self.coordinator.chat_log:
            item = QListWidgetItem(self.get_chat_text(chat_data))
            item.chat = chat_data
            self.question_list.addItem(item)
            
    def get_chat_text(self, chat):
        question = chat['question']
        date_asked = chat['time']
        
        # Customize the text representation for the list items
        return f'({date_asked}) {question}'
        
    def handle_item_clicked(self, item):
        # Handle when a list item is clicked
        question = item.chat['question']
        article = item.chat['article']
        answer = item.chat['answer']
        results_df = item.chat['results_df']
        
        print(f"Clicked on chat with question '{question}'")
        self.update_answer_area(question, article, answer, results_df)
        
    def update_answer_area(self, question, article, answer, results_json):
        results_df = pd.read_json(results_json, orient='split')
        
        cursor = self.answer_area.textCursor()
    
        # Clear the existing text
        self.answer_area.clear()
        
        # Set the font style for the headings
        heading_format = QTextCharFormat()
        heading_format.setFontWeight(QFont.Bold)
        
        # Set the font style for the headings
        text_format = QTextCharFormat()
        text_format.setFontWeight(QFont.Normal)
    
        # Add the question heading and text
        cursor.insertText("Question: \r\n", heading_format)
        cursor.insertText(question + "\r\n\r\n", text_format)
    
        # Add the answer heading and text
        cursor.insertText("Answer: \r\n", heading_format)
        cursor.insertText(answer + "\r\n\r\n", text_format)
    
        # Add the article heading and text
        cursor.insertText("Article: \r\n", heading_format)
        cursor.insertText(article + "\r\n\r\n", text_format)
    
        # list the documents where we found relevant chunks, with the chunks beneath
        # first - summarize the document list
        source_files = '\r\n'.join(results_df['source_document'].unique())
        cursor.insertText('Source files: ', heading_format)
        cursor.insertText(source_files + '\r\n\r\n', text_format)
        
        # now display the chunks
        cursor.insertText('Source data: ', heading_format)
        for i, row in results_df.iterrows():
            cursor.insertText(row['source_document'] + ' - ' + str(round(row['similarity'], 4)) + '\r\n', heading_format)
            cursor.insertText(row['text'] + '\r\n\r\n', text_format)
            
        self.answer_area.setTextCursor(cursor)
        self.answer_area.verticalScrollBar().setValue(0)
        
    def show_settings_window(self):
        settings_window = SettingsWindow(self, self.coordinator)
        settings_window.exec()
        
        self.startup_check()

class SettingsWindow(QDialog):
    class ColorDelegate(QStyledItemDelegate):
        def initStyleOption(self, option, index):
            super().initStyleOption(option, index)
            if index.column() == 1:
                value = index.data()
                if value is not None:
                    if value == 'True':
                        option.palette.setColor(QPalette.ColorRole.Highlight, QColor(Qt.green).lighter(130))
                    else:
                        option.palette.setColor(QPalette.ColorRole.Highlight, QColor(Qt.red).lighter(130))
                        
    def __init__(self, parent, app_coordinator):
        super().__init__(parent)
        # Set up the UIa
        self.setWindowTitle("Settings")
        self.setGeometry(100, 100, 800, 600)
        
        # .txt documents go here
        self.documents_folder = './documents'
        
        # create the empty folder on first run 
        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
        
        self.app_settings = AppSettings()
        
        # use the app_coordinator to get embeddings and chat 
        self.app_coordinator = app_coordinator

        self.init_ui()

    def init_ui(self):
        # Set up the UI elements
        layout = QVBoxLayout()

        # Create a table to display the list of .txt files and their embedding status
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(2)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setHorizontalHeaderLabels(["File", "Has Embeddings"])
        self.file_table.setItemDelegate(SettingsWindow.ColorDelegate())
        self.file_table.cellClicked.connect(self.file_table_clicked)
        layout.addWidget(self.file_table)

        # Add buttons to create and remove embeddings, and review existing embeddings
        self.create_embeddings_button = QPushButton("Create Embeddings")
        self.create_embeddings_button.clicked.connect(self.create_embeddings)
        self.create_embeddings_button.setEnabled(False)
        layout.addWidget(self.create_embeddings_button)

        self.remove_document_button = QPushButton("Remove Document")
        self.remove_document_button.clicked.connect(self.remove_document)
        layout.addWidget(self.remove_document_button)

        # Set up the main window with the layout
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setLayout(layout)
        
        # self.setCentralWidget(central_widget)

        # Load the list of files and their embedding status
        self.get_embedding_status()

    def get_embedding_status(self):
        # Load settings from the file
        settings = self.app_settings.get_settings()

        self.file_table.setRowCount(0)
        for document_name in os.listdir(self.documents_folder):
            if document_name.endswith('.txt'):
                row = self.file_table.rowCount()
                self.file_table.insertRow(row)

                has_embeddings = settings.get('embeddings', {}).get(document_name, False)

                self.file_table.setItem(row, 0, QTableWidgetItem(document_name))
                self.file_table.setItem(row, 1, QTableWidgetItem(str(has_embeddings)))


    def file_table_clicked(self, row, column):
        has_embeddings = self.file_table.item(row, 1).text() == 'True'
        self.create_embeddings_button.setEnabled(not has_embeddings)

    def create_embeddings(self):
        settings = self.app_settings.get_settings()
        
        # these are the row numbers
        rows = set([row.row() for row in self.file_table.selectedItems()])
        for row in rows:
            # get the filename from the selected row
            document_name = self.file_table.item(row, 0).text()
            # create the embeddings for the document
            self.app_coordinator.embedding_processor.create_embeddings(document_name)
            # sanity check the results
            has_embedding = self.app_coordinator.embedding_processor.has_embeddings(document_name)
    
            # Update the embedding status
            self.file_table.setItem(row, 1, QTableWidgetItem("True" if has_embedding else "False"))
            settings['embeddings'][document_name] = has_embedding
            
        self.app_settings.save_settings(settings)

    def remove_document(self):
        # the users document is not deleted, only the embeddings for the document are deleted
        # these are the row numbers
        rows = set([row.row() for row in self.file_table.selectedItems()])
        for row in rows:
            document_name = self.file_table.item(row, 0).text()
        
            settings = self.app_settings.get_settings()
            settings['embeddings'][document_name] = False
            
            # and the dataframe that holds the actual embeddings
            emb_df = self.app_coordinator.embedding_processor.emb_df
            self.app_coordinator.embedding_processor.emb_df = emb_df[emb_df["source_document"] != document_name].copy()
        
        # update the settings file
        self.app_settings.save_settings(settings)
        # save the updated dataframe of embeddings
        self.app_coordinator.embedding_processor.emb_df.to_json(self.app_coordinator.embedding_processor.embeddings_path, orient='index')
        # update embedding status on the ui
        self.get_embedding_status()


if __name__ == "__main__":
    # all UI functions go through AppCoordinator
    coordinator = AppCoordinator()
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    main_window = MainWindow(coordinator)
    main_window.show()

    sys.exit(app.exec())

