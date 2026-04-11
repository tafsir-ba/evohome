import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Clock, User, Building2, FileText, Sparkles, Send } from 'lucide-react';

export const RecentActivity = ({ items = [], onFocusCommand }) => {
  const navigate = useNavigate();

  const deduplicated = items.filter(
    (item, index, self) => self.findIndex((i) => i.title === item.title) === index
  ).slice(0, 6);

  if (deduplicated.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-8">
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
              <Sparkles className="w-6 h-6 text-primary" />
            </div>
            <h3 className="font-medium mb-1">Get Started</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-sm mx-auto">
              Upload a document or type a command above to start managing your projects.
            </p>
            <Button
              variant="outline"
              onClick={onFocusCommand}
              data-testid="cta-focus-command"
            >
              <Send className="w-4 h-4 mr-2" />
              Start with a Command
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const getIcon = (type) => {
    if (type === 'client') return User;
    if (type === 'project') return Building2;
    return FileText;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-outfit flex items-center gap-2">
          <Clock className="w-4 h-4 text-muted-foreground" />
          Recent Activity
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {deduplicated.map((item) => {
            const Icon = getIcon(item.type);
            return (
              <div
                key={item.id}
                className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-colors"
                onClick={() => navigate(item.path)}
                data-testid={`recent-item-${item.id}`}
              >
                <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.title}</p>
                  <p className="text-xs text-muted-foreground truncate">{item.subtitle}</p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};
