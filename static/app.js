function bulletinBoard() {
  return {
    title: '',
    content: '',
    category: '',
    posts: [],

    fetchPosts() {
      fetch('/posts')
        .then(res => res.json())
        .then(data => this.posts = data);
    },

    submitPost() {
      fetch('/posts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: this.title,
          content: this.content,
          category: this.category
        })
      });
      this.title = this.content = this.category = '';
    },

    init() {
      this.fetchPosts();
      const socket = io();
      socket.on('new_post', (data) => this.fetchPosts());
    }
  }
}