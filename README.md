## Installation
```bash
git clone https://github.com/flendersn/crosspoint-scr-sync
cd crosspoint-scr-sync
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Requires Python 3.10+. Tested on Linux.

## Create Instance
```python
from crosspoint_scr_sync import CrossPointDevice, SCRImage
x4 = CrossPointDevice()
```
You can optionally specify the IP address using the `host` argument. If not provided, auto-discovery will be used.
You can also overwrite the default screensaver directory with the `scr_path` argument (default: `/sleep`). By default, the library checks that this folder exists on the device — set `verify_scr_path=False` to skip this check.

## Upload Files
Upload screensavers from a local directory:
```python
screensavers = SCRImage.from_directory(directory="x4_scr", include_sub=True)  # Default: False
result = x4.upload_scrs(files=screensavers)
```
You can also create your own SCRImage instances instead of loading them from a directory:
```python
custom_scr = SCRImage(name="test.bmp", path="xyz.bmp")
x4.upload_scrs(files=custom_scr)
```
Or upload directly from a URL:
```python
result = x4.upload_scrs_from_url(
urls="https://x4epapers.lowio.xyz/output/37/cd/37cdb657ec9226e52ce4d7160367d36c.bmp",
keep_image=True  # Set to True to keep the downloaded image in the working directory. Default: False
)
```
## Delete & Sync
Delete screensavers from ereader:
```python
result = x4.delete_scrs(files=["spiderman.bmp", "Jar-Jar-Binks.bmp"])
```
List screensavers currently on the device:
```python
result = x4.get_scrs()
```
Compare local files with the device:
```python
local = SCRImage.from_directory("x4_scr")
diff = x4.check_diff(local_files=local)
print(diff["only_local"])   # exists locally, missing on device
print(diff["only_remote"])  # exists on device, missing locally
```
Sync a local directory with the device:
```python
local = SCRImage.from_directory("x4_scr")
result = x4.sync_scrs(local_files=local, keep_remote_diff=False)  # Default: True
```