from dataclasses import dataclass
from crosspoint_scr_sync import ws_client
import pathlib
import requests
import tempfile

@dataclass
class SCRImage:
    name: str
    path: str

    def __post_init__(self):
        self._validate_file()

    def _validate_file(self):
        path = pathlib.Path(self.path)
        if path.suffix.lower() != ".bmp":
            raise ValueError("This file type is not allowed.")
        if not path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        
    @classmethod
    def from_directory(cls, directory:str, include_sub:bool = False) -> list["SCRImage"]:
        """Returns a list of SCRImages by scanning a folder."""
        path = pathlib.Path(directory)
        files = path.rglob("*") if include_sub else path.iterdir()
        return [cls(name=file.name, path =str(file.resolve())) for file in files if file.is_file() and file.suffix.lower() == ".bmp"]

class CrossPointDevice:
    def __init__(self, host:str="", port:int=80, scr_path:str="/sleep", verify_path:bool=True):
        self.device_host = host
        self.device_port = port
        self.scr_path = scr_path
        self.is_connected = False   
        self.timeout = 5
        if not host:
            self._detect_managed_devices()
        
        self.device_url = f"http://{self.device_host}:{self.device_port}"

        self._test_connection()

        if verify_path:
            self.verify_scr_path()

    def _discover(self) -> tuple[str | None, int | None]:
        host, _ = ws_client.discover_device(
            timeout=1.0,
        )
        if host:
            return host, 80 # use HTTP Port
        return None, None

    def _detect_managed_devices(self) -> None:
        host, port = self._discover()
        if host and port:
            self.device_host = host
            self.device_port = port
        else:
            raise ConnectionError(
                "No device found during discovery."
                "Check that the device web server is running and the device is connected to the same network."
            )

    def _test_connection(self) -> None:
        try:
            r = requests.get(self.device_url, timeout=self.timeout)
            r.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Connection failed: {e}") from e 
        self.is_connected = True

    def verify_scr_path(self):
        """Creates SCR folder if it doesn't exist, ignores 400 (already exists)"""
        if not self.is_connected:
            raise ConnectionError("Device is not connected")
        
        url = f"{self.device_url}/mkdir"
        folder_name = self.scr_path.strip("/")
        
        r = requests.post(url, data={"name": folder_name, "path": "/"}, timeout=self.timeout)
        
        if r.status_code not in (200, 400):
            raise RuntimeError(f"Failed to verify or create SCR directory: {r.status_code}")
            

    
    def upload_scrs(self, files:list["SCRImage"] | SCRImage) -> dict[str, list[str]]:
            """Uploads File to SD Card of Crosspoint Device, existing files 
            with the same name will be overwritten"""
            if not self.is_connected:
                raise ConnectionError("Device is not connected")
            
            if isinstance(files, SCRImage):
                files = [files]

            url = f"{self.device_url}/upload"
            params = {"path": self.scr_path}

            result = {"success":[],"failed":[]}
            for file in files:
                with open(file.path, 'rb') as f:
                    r = requests.post(url, params=params, files={"file": f}, timeout=self.timeout)
                if r.status_code == 200:
                    result["success"].append(file.name)
                else:
                    result["failed"].append(file.name)
            return result
    
    def upload_scrs_from_url(self, urls:list[str] | str, keep_image:bool=False) -> dict[str, list[str]]:
        """Downloads file to a temporary directory and calls upload_scr method """
        if isinstance(urls, str):
            urls = [urls]

        images = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for url in urls:
                filename = pathlib.Path(url).name

                if keep_image:
                    save_path = pathlib.Path("./") / filename
                else:
                    save_path = pathlib.Path(tmpdir) / filename

                r = requests.get(url, stream=True, timeout=self.timeout)
                r.raise_for_status()

                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                images.append(SCRImage(name=filename, path=str(save_path)))
            return self.upload_scrs(images)
        
    def delete_scrs(self, files:list | str) -> dict[str, list[str]]:
        """Deletes SCR files """
        if not self.is_connected:
            raise ConnectionError("Device is not connected")
        if isinstance(files, str):
            files = [files]
        result = {"success":[],"failed":[]}
        url = f"{self.device_url}/delete" 
        for file in files:
            data = {
                "path": f"{self.scr_path}/{file}",
                "type": "file"      
                }
            r = requests.post(url=url, data=data, timeout=self.timeout)
            if r.status_code == 200:
                result["success"].append(file)
            else:
                result["failed"].append(file)
        return result

    def get_scrs(self) -> list[str]:
        """Returns names of files in sleep directory"""
        url = f"{self.device_url}/api/files"
        params = {"path": self.scr_path}
        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return [d["name"] for d in data if not d["isDirectory"]] if data else []

    def check_diff(self, local_files: list["SCRImage"]) -> dict[str, list[str] | list[SCRImage]]:
        """Returns (files only local, files only remote)"""
        remote_files = set(self.get_scrs())
        local_names = {f.name for f in local_files}

        only_local = [f for f in local_files if f.name not in remote_files]
        only_remote = [f for f in remote_files if f not in local_names]
        return {"only_local": only_local, "only_remote": only_remote}

    def sync_scrs(self, local_files: list["SCRImage"], keep_remote_diff: bool = True) -> dict[str, list[str]]:
        """Syncs local files with remote device"""
        diff = self.check_diff(local_files)
        only_local = diff["only_local"]
        only_remote = diff["only_remote"]

        deleted_files = []
        if not keep_remote_diff:
            result = self.delete_scrs(only_remote)
            deleted_files = result["success"]

        upload_result = self.upload_scrs(only_local)
        return {
            "uploaded": upload_result["success"],
            "upload_failed": upload_result["failed"],
            "deleted": deleted_files
        }

