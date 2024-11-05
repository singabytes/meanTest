import cv2
import qrcode
import os
import textwrap
import hashlib
import time
import sys 
from pyzbar.pyzbar import decode

######
# Create QR video from input document
# max_qr_msg_length = 1000 - longueur text by QR
# txt_to_encode = r'C:\temp\world192-5000.txt' - text a encoder
# qr_path = 'C:\\temp\\frames2encode\\' - folder to dump QR (frames for video)
# video_path = 'C:\\temp\\videos' - folder for the output video
# video_name = 'video-encoded.avi' - name of the video output
#######

txt_to_encode = r'C:\temp\world192-5000.txt'

qr_path = 'C:\\temp\\frames2encode\\'
video_path = 'C:\\temp\\videos'
video_name = 'video-encoded.avi'
max_qr_msg_length = 1000

def delete_all_files(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

def read_qr_code(filename):
    try:
        img = cv2.imread(filename)
        barcodes = decode(img)
        return barcodes[0].data.decode()
    except Exception as e:
        print(e)
        return

delete_all_files(qr_path)

# read file to encode
with open(txt_to_encode) as f:
    msg = f.read()

print(len(msg))
print('---------------------------------')
print(msg)
print('---------------------------------')

print('Message total length = {}'.format(len(msg)))

buffer = []
count = 0
frame_number = 0

msg1 = msg.replace('\n', '*')
msg2 = msg1.replace(' ', '#')

buffer = textwrap.wrap(msg2, max_qr_msg_length, break_on_hyphens=False)

print('Total number of frame = {}'.format(len(buffer)))

frame_number = 0
for chunck in buffer:
        #qr = qrcode.make(chunck, version=30, border=100, error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr_generator = qrcode.QRCode(
        #version=30,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        #box_size=QRCODE_BOX_SIZE,
        border=10)
        qr_generator.add_data(chunck)
        img = qr_generator.make(fit=True)
        img = qr_generator.make_image(fill_color="black", back_color="white")
        path = os.path.join(qr_path,'frame-' + str(frame_number) + '.png')
        img.save(path)
        #check 
        test = read_qr_code(path)
        if (test != chunck):
            print('-------- error encoding -------')
            print(f'source : {chunck}')
            print(f'encode : {test}')
            sys.exit()
        #
        print('Writing frame : {}'.format(frame_number))
        frame_number = frame_number + 1
        print(chunck)
        print(len(chunck))
        print('')
        #time.sleep(1)
#
# Generate video
#
print('Generating video...')
images = [img for img in os.listdir(qr_path) if img.endswith('.png')]
frame = cv2.imread(os.path.join(qr_path, images[0]))
height_ref, width_ref, layers = frame.shape

print(height_ref, width_ref)

video = cv2.VideoWriter(os.path.join(video_path, video_name), 0, 1, (width_ref, height_ref))

for i in range(0, frame_number + 1):
    image = 'frame-' + str(i) + '.png'
    print('Add frame {}'.format(image))
    frame = cv2.imread(os.path.join(qr_path, image))
    frame = cv2.resize(frame, (height_ref, width_ref),
               interpolation = cv2.INTER_LINEAR)
    height, width, layers = frame.shape
    print(height, width)
    video.write(frame)

cv2.destroyAllWindows()
video.release()

print('--- md5 ---')
print(txt_to_encode)
print(hashlib.md5(open(txt_to_encode, 'rb').read()).hexdigest())