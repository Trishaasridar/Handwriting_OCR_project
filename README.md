# Handwriting_OCR_project
This Python/Flask application provides a web interface for performing **OCR on handwritten notes** using PaddleOCR, storing the results and original image in **MySQL**, and enabling search with a unique animated book interface.

# To use the project:
## Execute the following command in mysql:
CREATE DATABASE OCR;
USE OCR;
CREATE TABLE ocr_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_name VARCHAR(255) NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    image_blob MEDIUMBLOB NOT NULL, 
    date DATE NOT NULL,
    time TIME NOT NULL,
    content LONGTEXT
);
## Then,
1. Install the requirements mentioned in the requirements.txt file
2. run the app.py file
3. navigate to the url port produced from the terminal to access the project
4. upload the image and fill the details and click on convert to text button. Then in the left window, the result will be displayed
   
# To get the previous data from mysql:
1. scroll down and fill the student name or the course name.
2. click on look button to display the data from the database
