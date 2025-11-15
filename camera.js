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
  }
};