---
layout: default
title: BTC Pulse Blog
---

<div class="content-wrapper">
  <section class="layout-main blog-index">
    <header class="blog-header">
      <h1>BTC Pulse Blog</h1>
      <p>Research notes, model updates, and market structure observations.</p>
    </header>
    <ul class="blog-list">
      {% for post in site.posts %}
      <li class="blog-card">
        <a class="blog-card__title" href="{{ site.baseurl }}{{ post.url }}">{{ post.title }}</a>
        <div class="blog-card__meta">{{ post.date | date: "%Y-%m-%d" }}{% if post.author %} • {{ post.author }}{% endif %}</div>
        {% if post.excerpt %}
        <p class="blog-card__excerpt">{{ post.excerpt | strip_html | truncate: 180 }}</p>
        {% endif %}
      </li>
      {% endfor %}
    </ul>
  </section>
</div>
