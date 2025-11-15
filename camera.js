// NOTE: Make sure to reload the browser with cache disabled after making changes to this file.
export default {
  template: `
    <video ref="video" autoplay playsinline muted style="width: 100%; height: auto;"></video>
  `,
  mounted() {
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(stream => {
        this.$refs.video.srcObject = stream;
      })
      .catch(err => {
        console.error('Error accessing camera:', err);
      });
  },
  beforeUnmount() {
    if (this.$refs.video && this.$refs.video.srcObject) {
      const stream = this.$refs.video.srcObject;
      const tracks = stream.getTracks();
      tracks.forEach(track => track.stop());
    }
  },
  methods: {
    capture() {
      const canvas = document.createElement('canvas');
      canvas.width = this.$refs.video.videoWidth;
      canvas.height = this.$refs.video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(this.$refs.video, 0, 0);
      const dataURL = canvas.toDataURL('image/jpeg');
      fetch('/api/save_photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ b64url: dataURL })
      }).then(response => response.json()).then(data => {
        console.log('Photo saved:', data);
      }).catch(err => {
        console.error('Error saving photo:', err);
      });
      // Play shutter sound
      new Audio('/assets/camera-shutter.mp3').play();
    }
  }
};