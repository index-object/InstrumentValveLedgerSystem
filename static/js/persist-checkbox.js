(function() {
  var STORAGE_KEY = 'checked_ids_' + window.location.pathname

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

  function updateSelectAll() {
    var checkboxes = document.querySelectorAll('.item-checkbox')
    var allChecked = checkboxes.length > 0 && Array.from(checkboxes).every(function(cb) { return cb.checked })
    var el = document.getElementById('selectAll')
    if (el) el.checked = allChecked
    var el2 = document.getElementById('selectAllTop')
    if (el2) el2.checked = allChecked
  }

  function updateCountDisplay() {
    var ids = getIds()
    var count = ids.length
    var els = document.querySelectorAll('#selectedCount, #selectedCountTable')
    els.forEach(function(el) { el.textContent = count })
  }

  window.updateSelectedCount = updateCountDisplay

  document.addEventListener('DOMContentLoaded', function() {
    var stored = getIds()
    document.querySelectorAll('.item-checkbox').forEach(function(cb) {
      if (stored.indexOf(cb.value) !== -1) {
        cb.checked = true
      }
    })
    updateSelectAll()
    updateCountDisplay()
  })

  document.addEventListener('change', function(e) {
    if (e.target.matches('.item-checkbox')) {
      var stored = getIds()
      var val = e.target.value
      if (e.target.checked) {
        if (stored.indexOf(val) === -1) stored.push(val)
      } else {
        stored = stored.filter(function(id) { return id !== val })
      }
      setIds(stored)
      updateSelectAll()
      updateCountDisplay()
    }

    if (e.target.id === 'selectAll' || e.target.id === 'selectAllTop') {
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
      updateCountDisplay()
    }
  })

  document.addEventListener('submit', function(e) {
    var form = e.target
    if (form.id !== 'batchForm' && form.id !== 'batch-form') return

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
