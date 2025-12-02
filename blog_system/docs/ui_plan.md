# 前端重构预备方案（Phase 3）

## 框架与基础设施
- **CSS 框架**：Bootstrap 5.3（CDN，引导响应式栅格、组件状态与适配性）
- **图标支持**：Font Awesome 6.4（统一图标库，降低自定义成本）
- **字体体系**：Google Fonts _Inter_，配合 CSS 变量统一字号、行距
- **主题脚本**：`static/js/theme.js` 实现本地存储 + prefers-color-scheme 自动感知
- **SPA 过渡**：`static/js/spa.js` 预留导航高亮、后续前端路由事件总线

## 色彩与视觉
- **主色 (Primary)**：#6366F1（灵感紫），加深色 #4F46E5
- **强调 (Accent)**：渐变 `linear-gradient(135deg, #6366F1 → #8B5CF6 → #EC4899)`
- **成功/活力**：#34D399（成功）、#F97316（创意/提示）
- **背景**：亮色 `#F5F6FA`，夜间 `#0F172A`
- **文本**：基础 `#1F2937`，暗色 `#E2E8F0`
- **表面**：半透明玻璃拟态，配合 `backdrop-filter`（亮/暗均调整）

## 模板拆分结构
```
templates/
└── layout.html          # 顶层布局：导航、主题切换、助手、页脚
    ├── {navbar_links}       -> 动态导航列表
    ├── {header_actions}     -> 登录/用户信息按钮区域
    ├── {main_content}       -> 页面主体内容
    ├── {extra_css_links}    -> 页面级额外样式
    └── {extra_js_scripts}   -> 页面级额外脚本
```

后续页面（如 `index.html`、`post.html` 等）将仅关注 `main_content`，通过 `TemplateRenderer` 扩展在渲染阶段写入布局。

## 计划中的组件
- **全局导航**：顶部固定 + 渐变品牌字 + 模式切换按钮
- **卡片矩阵**：文章卡片、仪表盘板块统一圆角 24px + 投影层级
- **评论树 / 聊天消息**：多级缩进、表情支持、微交互 hover
- **性能监测面板**：Chart.js 折线/面积图，自定义图例、实时刷新占位
- **页面助手**：动画状态头像（SVG 变体）、对话泡泡按钮
- **主题切换**：按钮动画、存储在 localStorage，支持半夜自动切换

## 后续适配步骤
1. 扩展 `TemplateRenderer` 以支持 layout + slot 渲染
2. 逐页迁移（首页、文章详情、仪表板、私信、订阅、性能面板）
3. 整合 Chart.js、加载骨架、按钮动画等
4. 引入轻量的前端状态管理（事件驱动，后期可选 htmx / Alpine.js）

