import sys
import os

# Add parent directory to path so we can import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.imagekit_service import upload_audio, delete_audio

file_path = '/Users/ujjwal/Desktop/code/interview-coach/backend/temp/closure.mp3'
file_name = 'closure.mp3'

print('Uploading audio...')
result = upload_audio(file_path, file_name)
print(f'URL: {result["url"]}')
print(f'File ID: {result["file_id"]}')

# Delete after test
file_id = result['file_id']
print(f'\nDeleting...')
success = delete_audio(file_id)
print(f'Delete success: {success}')
print('\nTest completed!')