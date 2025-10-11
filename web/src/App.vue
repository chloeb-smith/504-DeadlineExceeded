<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getHealth, getHello } from "./api";

const health = ref<any>(null);
const hello = ref<any>(null);

onMounted(async () => {
  health.value = await getHealth();
  hello.value = await getHello();
});
</script>

<template>
  <main style="max-width: 680px; margin: 2rem auto; font-family: system-ui, sans-serif;">
    <h1>Vue + Flask Skeleton</h1>
    <section>
      <h3>API Health</h3>
      <pre>{{ health }}</pre>
      <h3>Hello</h3>
      <pre>{{ hello }}</pre>
    </section>
  </main>
</template>
