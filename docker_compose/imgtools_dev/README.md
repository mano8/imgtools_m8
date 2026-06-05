# ImgTools_m8 dev

## Test Cuda

```bash
docker-compose exec upscaler bash
python3 - <<EOF
import cv2
print("OpenCV version:", cv2.__version__)
print("CUDA devices:", cv2.cuda.getCudaEnabledDeviceCount())
EOF
```
