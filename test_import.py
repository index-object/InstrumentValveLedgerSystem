print('step 1')  
from app.utils.importer import safe_read_excel  
print('step 2')  
data = safe_read_excel('导入台账示例.xlsx')  
print('step 3')  
print('sheets:', [d['sheet'] for d in data])  
