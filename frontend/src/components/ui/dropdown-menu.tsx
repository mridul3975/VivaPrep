// Adapted from shadcn/ui's Base UI dropdown-menu; uses RepoViva's theme.
import { Menu } from '@base-ui/react/menu'
import Icon from '../Icon'
import './dropdown-menu.css'
export const DropdownMenu = Menu.Root
export const DropdownMenuTrigger = Menu.Trigger
export const DropdownMenuRadioGroup = Menu.RadioGroup
export function DropdownMenuContent({ children, ...props }: Menu.Popup.Props) {
  return <Menu.Portal><Menu.Positioner sideOffset={6} align="start" className="language-menu-positioner"><Menu.Popup data-slot="dropdown-menu-content" className="language-menu" {...props}>{children}</Menu.Popup></Menu.Positioner></Menu.Portal>
}
export function DropdownMenuRadioItem({ children, ...props }: Menu.RadioItem.Props) {
  return <Menu.RadioItem data-slot="dropdown-menu-radio-item" className="language-menu-item" {...props}><span>{children}</span><Menu.RadioItemIndicator><Icon name="check" size={16} /></Menu.RadioItemIndicator></Menu.RadioItem>
}
