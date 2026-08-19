# Report Template Placeholders

The DOCX template must keep these placeholders:

- `{{xxxx}}` (appears twice, ordered values: project code, year)
- `{{xx}}` (appears twice, ordered values: month, day)
- `{{补充时间}}`
- `{{测试用例1名称}}`
- `{{测试用例2名称}}`
- `{{xxxxx}}`
- `{{}}` repeated in each test block and summary block

The reporter clones the block containing `{{测试用例2名称}}` to render test item 3 and above as same table format.

## Screenshot Embedding Notes

- Each test item's remarks may include internal markers like `[[E2E_CASE_SCREEN_1]]`.
- These markers are replaced at DOCX render time with real embedded Word images (`w:drawing`).
- Do not remove remarks cell placeholders (`{{}}`) in case tables, otherwise screenshot injection cannot land in the expected cell.

Keep the summary heading and total lines in document:

- `测试结果` (Heading 2 paragraph)
- `总用例：`
- `通过：`
- `失败：`
- `跳过：`
- `超时：`
- `中断：`
