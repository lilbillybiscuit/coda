import time

import docker
from docker.models.containers import Container
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any, Union
import tempfile
import os
import logging
import yaml
from typing_extensions import TypeAlias
from docker.errors import NotFound, APIError, ImageNotFound
import io
import tarfile

logger = logging.getLogger(__name__)

# Type aliases
PathStr: TypeAlias = str
EnvVars: TypeAlias = Dict[str, str]
VolumeConfig: TypeAlias = Dict[str, Dict[str, str]]
CommandOutput: TypeAlias = Tuple[str, str]


class DockerConfig:
    """Configuration for Docker environment"""

    def __init__(self, config_file: Optional[PathStr] = None) -> None:
        self.config: Dict[str, Any] = {
            "image": "coda:latest",
            "container_name": "coda_env",
            "dockerfile_path": "./Dockerfile",
            "volumes": {
                "workspace": "/workspace",
                "scripts": "/scripts",
                "logs": "/logs"
            },
            "environment": {},
            "working_dir": "/workspace",
            "network": "bridge",
            "auto_remove": True,
            "detach": True
        }

        if config_file and os.path.exists(config_file):
            print("Using config file")
            with open(config_file) as f:
                self.config.update(yaml.safe_load(f))


class DockerEnvironment:
    def __init__(self, config: Optional[DockerConfig] = None) -> None:
        self.config: DockerConfig = config or DockerConfig()
        self.client: docker.DockerClient = docker.from_env()
        self.container: Optional[Container] = None

        # Set up volume directories with proper structure
        base_path: Path = Path("./docker_data").absolute()
        base_path.mkdir(parents=True, exist_ok=True)

        # Initialize container_volumes
        self.container_volumes = {}
        for name, mount_point in self.config.config["volumes"].items():
            volume_path = base_path / name
            volume_path.mkdir(parents=True, exist_ok=True)
            # Ensure host directory has proper permissions
            os.chmod(volume_path, 0o777)

            self.container_volumes[str(volume_path)] = {
                'bind': mount_point,
                'mode': 'rw'
            }

        self._ensure_container()

    def _build_image(self) -> None:
        """Build Docker image if it doesn't exist"""
        try:
            logger.info(f"Building Docker image: {self.config.config['image']}")
            self.client.images.build(
                path=".",
                tag=self.config.config["image"],
                dockerfile=self.config.config["dockerfile_path"]
            )
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            raise

    def _ensure_image(self) -> None:
        """Ensure Docker image exists, build if necessary"""
        try:
            self.client.images.get(self.config.config["image"])
            logger.info(f"Found existing Docker image: {self.config.config['image']}")
        except ImageNotFound:
            logger.info(f"Image {self.config.config['image']} not found, building...")
            self._build_image()

    def _ensure_container(self) -> None:
        """Ensure container exists and is running"""
        try:
            # Try to get existing container
            container = self.client.containers.get(self.config.config["container_name"])

            # Check container state
            container.reload()  # Refresh container state

            if container.status != "running":
                logger.info(f"Starting existing container: {self.config.config['container_name']}")
                container.start()

            self.container = container
            logger.info(f"Using existing container: {self.config.config['container_name']}")

        except NotFound:
            logger.info(f"Container {self.config.config['container_name']} not found, creating new one")
            self._ensure_image()
            self.container = self._create_container()

        except APIError as e:
            logger.error(f"Docker API error: {e}")
            # Try to clean up and recreate
            self._cleanup_container()
            self._ensure_image()
            self.container = self._create_container()

    def _cleanup_container(self) -> None:
        """Clean up existing container if needed"""
        try:
            container = self.client.containers.get(self.config.config["container_name"])
            logger.info(f"Removing existing container: {self.config.config['container_name']}")
            container.remove(force=True)
        except NotFound:
            pass
        except APIError as e:
            logger.error(f"Error cleaning up container: {e}")

    def _create_container(self) -> Container:
        """Create a new container"""
        logger.info(f"Creating new container: {self.config.config['container_name']}")

        try:
            # First clean up any existing container
            self._cleanup_container()

            # Create new container
            container = self.client.containers.run(
                self.config.config["image"],
                name=self.config.config["container_name"],
                volumes=self.container_volumes,
                environment=self.config.config["environment"],
                working_dir=self.config.config["working_dir"],
                network=self.config.config["network"],
                detach=True,
                auto_remove=False,
                tty=True,
                stdin_open=True,
                user="0"  # Run as root
            )

            # Wait for container to be ready
            container.reload()
            while container.status != "running":
                time.sleep(0.1)
                container.reload()

            # Ensure workspace has correct permissions
            container.exec_run("chmod -R 777 /workspace")

            return container

        except APIError as e:
            logger.error(f"Failed to create container: {e}")
            raise


    def execute(self,
                command: str,
                workdir: Optional[PathStr] = None,
                environment: Optional[EnvVars] = None,
                stream: bool = False) -> CommandOutput:
        """Execute a command in the container"""
        if not self.container:
            raise RuntimeError("No container available")

        try:
            # Ensure container is running
            self.container.reload()
            if self.container.status != "running":
                logger.info("Container not running, attempting to start...")
                self.container.start()
                self.container.reload()

            result = self.container.exec_run(
                cmd=command,
                workdir=workdir or self.config.config["working_dir"],
                environment=environment,
                stream=stream,
                demux=True
            )

            if stream:
                return self._handle_stream(result)

            stdout: str = result.output[0].decode() if result.output[0] else ""
            stderr: str = result.output[1].decode() if result.output[1] else ""

            return stdout, stderr

        except (NotFound, APIError) as e:
            logger.error(f"Command execution failed: {e}")
            # Try to recover by ensuring container
            self._ensure_container()
            raise RuntimeError(f"Container error: {e}")

    def cleanup(self) -> None:
        """Clean up resources immediately"""
        if self.container:
            try:
                logger.info("Stopping container...")
                self.container.stop(timeout=1)  # Short timeout for quick shutdown
                logger.info("Removing container...")
                self.container.remove(force=True)  # Force removal
                self.container = None
            except (NotFound, APIError) as e:
                logger.error(f"Cleanup failed: {e}")
            finally:
                # Ensure client is closed
                if hasattr(self, 'client'):
                    logger.info("Closing Docker client...")
                    self.client.close()

    def force_cleanup(self) -> None:
        """Force cleanup of all resources"""
        try:
            # Clean up any containers with our name
            for container in self.client.containers.list(all=True):
                if container.name == self.config.config["container_name"]:
                    logger.info(f"Force removing container: {container.name}")
                    container.remove(force=True)

            # Clean up any related volumes
            for volume in self.client.volumes.list():
                if volume.name.startswith("coda_"):
                    logger.info(f"Removing volume: {volume.name}")
                    volume.remove(force=True)

        except Exception as e:
            logger.error(f"Force cleanup error: {e}")
        finally:
            self.client.close()

    def __enter__(self) -> 'DockerEnvironment':
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        self.cleanup()

    def copy_to_container(self, content: Union[str, bytes], dest_path: str) -> None:
        """Copy content to a file in the container"""
        if not self.container:
            raise RuntimeError("No container available")

        try:
            # Ensure content is bytes
            if isinstance(content, str):
                content = content.encode()

            # Create a tar stream containing the file
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w:gz') as tar:
                tarinfo = tarfile.TarInfo(name=os.path.basename(dest_path))
                tarinfo.size = len(content)
                tar.addfile(tarinfo, io.BytesIO(content))

            # Reset stream position
            tar_stream.seek(0)

            # Copy the tar stream to the container
            self.container.put_archive(
                path=os.path.dirname(dest_path),
                data=tar_stream
            )

            logger.info(f"Successfully copied content to {dest_path}")

        except Exception as e:
            logger.error(f"Failed to copy content to container: {e}")
            raise

    def copy_from_container(self, src_path: str, local_path: str) -> None:
        """Copy file from container to local filesystem"""
        if not self.container:
            raise RuntimeError("No container available")

        try:
            # Get file as tar stream from container
            bits, stat = self.container.get_archive(src_path)

            # Create local directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Write tar stream to temporary file
            with tempfile.NamedTemporaryFile() as tmp:
                for chunk in bits:
                    tmp.write(chunk)
                tmp.seek(0)

                # Extract file from tar
                with tarfile.open(fileobj=tmp) as tar:
                    member = tar.next()  # Get first (and should be only) member
                    if member:
                        with tar.extractfile(member) as source, open(local_path, 'wb') as target:
                            target.write(source.read())

            logger.info(f"Successfully copied {src_path} to {local_path}")

        except Exception as e:
            logger.error(f"Failed to copy from container: {e}")
            raise

    def execute_script(self, script: str, working_directory: str) -> Tuple[str, str]:
        """Execute a script in the container"""
        if not self.container:
            raise RuntimeError("No container available")

        try:
            # Create scripts directory if it doesn't exist
            script_dir = self.volumes["scripts"]["bind"]
            self.execute(f"mkdir -p {script_dir}")

            # Generate unique script name
            script_name = f"task_{os.urandom(4).hex()}.sh"
            script_path = os.path.join(script_dir, script_name)

            # Copy script to container
            self.copy_to_container(script, script_path)

            # Make script executable
            self.execute(f"chmod +x {script_path}")

            # Execute script
            return self.execute(
                f"bash {script_path}",
                workdir=working_directory
            )

        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return "", str(e)
