<template>
  <section class="page" data-module="pothole">
    <header class="page-head">
      <div>
        <h2>坑槽修补管理</h2>
        <p class="page-desc">维护修补单，围绕修补单号、所在路段、修补面积、修补材料做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记修补单</button>
        <button class="btn" type="button" @click="exportRows">导出坑槽修补清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ cellValue(row, column) ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无坑槽修补数据，可先登记修补单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条坑槽修补记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatsSummary = Record<string, number>

const ENDPOINT = '/api/pothole'
const columns = ["修补单号", "所在路段", "修补面积", "修补材料", "用料数量", "作业班组", "完成日期", "修补状态"]
const actions = ["安排修补", "确认完成", "取消修补"]
const statuses = ["待安排", "修补中", "已完成", "已取消"]
const stats = ref([
  { label: "待安排修补", value: 0 },
  { label: "本月修补面积", value: 0 },
  { label: "取消单数", value: 0 },
])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function cellValue(row: Row, column: string) {
  return column === '用料数量' ? row['工程量'] : row[column]
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '修补单登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('坑槽修补动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '坑槽修补操作失败'
  }
}

async function loadStats() {
  const response = await request(`${ENDPOINT}/stats`)
  if (!response.ok) {
    throw new Error('修补单统计读取失败')
  }
  const payload = await response.json() as StatsSummary
  stats.value = stats.value.map(item => ({ ...item, value: payload[item.label] ?? item.value }))
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('修补单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    try {
      await loadStats()
    } catch {
      // 统计卡片保持默认值，不影响列表读取结果。
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '坑槽修补列表读取失败'
  }
}

onMounted(reload)
</script>
