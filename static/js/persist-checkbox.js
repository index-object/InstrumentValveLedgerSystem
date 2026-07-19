(function() {
  var STORAGE_KEY = 'checked_ids_' + window.location.pathname
  var SELECT_ALL_KEY = 'select_all_' + window.location.pathname

  function isSelectAllMode() {
    return sessionStorage.getItem(SELECT_ALL_KEY) === 'true'
  }

  function setSelectAllMode(active) {
    if (active) {
      sessionStorage.setItem(SELECT_ALL_KEY, 'true')
      sessionStorage.removeItem(STORAGE_KEY)
    } else {
      sessionStorage.removeItem(SELECT_ALL_KEY)
    }
  }

  function getIds() {
    try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]') }
    catch(e) { return [] }
  }

  function setIds(ids) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
  }

  function getVisibleValues() {
    return Array.from(document.querySelectorAll('.item-checkbox')).map(function(cb) { return cb.value })
  }

  function getTotalCount() {
    var el = document.getElementById('totalCount')
    return el ? parseInt(el.textContent) || 0 : 0
  }

  function syncCheckboxes() {
    var checked = isSelectAllMode()
    document.querySelectorAll('.item-checkbox').forEach(function(cb) { cb.checked = checked })
  }

  function updateSelectAll() {
    var checkboxes = document.querySelectorAll('.item-checkbox')
    var allVisible = document.querySelectorAll('.item-checkbox').length > 0
    var allChecked = allVisible && Array.from(checkboxes).every(function(cb) { return cb.checked })
    var ids = ['selectAllTop', 'selectAllTable']
    ids.forEach(function(id) {
      var el = document.getElementById(id)
      if (el) el.checked = allChecked
    })
    var toolbar = document.getElementById('selectAll')
    if (toolbar) toolbar.checked = isSelectAllMode() || allChecked
  }

  function updateCountDisplay() {
    var count = isSelectAllMode() ? getTotalCount() : getIds().length
    var els = document.querySelectorAll('#selectedCount, #selectedCountTable')
    els.forEach(function(el) { el.textContent = count })
  }

  window.updateSelectedCount = updateCountDisplay
  window.isSelectAllMode = isSelectAllMode

  document.addEventListener('DOMContentLoaded', function() {
    if (isSelectAllMode()) {
      document.querySelectorAll('.item-checkbox').forEach(function(cb) { cb.checked = true })
    } else {
      var stored = getIds()
      document.querySelectorAll('.item-checkbox').forEach(function(cb) {
        if (stored.indexOf(cb.value) !== -1) cb.checked = true
      })
    }
    updateSelectAll()
    updateCountDisplay()
  })

  document.addEventListener('change', function(e) {
    /* 逐条勾选 */
    if (e.target.matches('.item-checkbox')) {
      if (isSelectAllMode()) {
        if (!e.target.checked) {
          setSelectAllMode(false)
          var visible = getVisibleValues()
          var stored = visible.filter(function(id) { return id !== e.target.value })
          setIds(stored)
        }
      } else {
        var stored = getIds()
        var val = e.target.value
        if (e.target.checked) {
          if (stored.indexOf(val) === -1) stored.push(val)
        } else {
          stored = stored.filter(function(id) { return id !== val })
        }
        setIds(stored)
      }
      updateSelectAll()
      updateCountDisplay()
    }

    /* 工具栏全选 — 跨页 */
    if (e.target.id === 'selectAll') {
      if (e.target.checked) {
        setSelectAllMode(true)
        document.querySelectorAll('.item-checkbox').forEach(function(cb) { cb.checked = true })
      } else {
        setSelectAllMode(false)
        document.querySelectorAll('.item-checkbox').forEach(function(cb) { cb.checked = false })
        setIds([])
      }
      updateSelectAll()
      updateCountDisplay()
    }

    /* 表头全选 — 仅当前页 */
    if (e.target.id === 'selectAllTop' || e.target.id === 'selectAllTable') {
      if (isSelectAllMode()) {
        if (!e.target.checked) {
          setSelectAllMode(false)
          setIds([])
          document.querySelectorAll('.item-checkbox').forEach(function(cb) { cb.checked = false })
        }
      } else {
        var stored = getIds()
        var visible = getVisibleValues()
        if (e.target.checked) {
          visible.forEach(function(id) {
            if (stored.indexOf(id) === -1) stored.push(id)
          })
        } else {
          stored = stored.filter(function(id) { return visible.indexOf(id) === -1 })
        }
        setIds(stored)
        document.querySelectorAll('.item-checkbox').forEach(function(cb) { cb.checked = e.target.checked })
      }
      updateSelectAll()
      updateCountDisplay()
    }
  })

  document.addEventListener('submit', function(e) {
    var form = e.target
    if (form.id !== 'batchForm' && form.id !== 'batch-form') return

    if (isSelectAllMode()) return

    var stored = getIds()
    if (stored.length === 0) return

    form.querySelectorAll('input[name="ids"]').forEach(function(input) {
      if (input.type === 'checkbox') input.remove()
    })
    stored.forEach(function(id) {
      var input = document.createElement('input')
      input.type = 'hidden'
      input.name = 'ids'
      input.value = id
      form.appendChild(input)
    })

    sessionStorage.removeItem(STORAGE_KEY)
  })
})()
